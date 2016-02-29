import inspect
import json
import traceback
import urllib
import urllib.parse

import base64
import functools
from django.conf import settings
from django.db.models import Q

import fedoralink
from dateutil.parser import parse
from elasticsearch import Elasticsearch
from rdflib import Literal, URIRef, RDF

from fedoralink.fedorans import FEDORA
from fedoralink.fields import LangTextAreaField
from fedoralink.indexer import Indexer, IndexedField, FEDORA_TYPE_FIELD, FEDORA_PARENT_FIELD
from fedoralink.models import IndexableFedoraObject
from fedoralink.rdfmetadata import RDFMetadata
from fedoralink.utils import url2id, id2url


def gc(map, key, default):
    if key in map:
        return map[key]
    map[key] = default
    return default

class ElasticIndexer(Indexer):

    def __init__(self, repo_conf):
        url = urllib.parse.urlsplit(repo_conf['SEARCH_URL'])
        self.index_name = url.path

        while self.index_name.startswith('/'):
            self.index_name = self.index_name[1:]
        while self.index_name.endswith('/'):
            self.index_name = self.index_name[:-1]

        self.es = Elasticsearch(({"host": url.hostname, "port": url.port}, ))

        if not self.es.indices.exists(self.index_name):
            self.es.indices.create(index=self.index_name)

    def save_mapping(self, class_name, mapping):
        return self.es.indices.put_mapping(index=self.index_name, doc_type=class_name, body=mapping)

    def get_mapping(self, class_name):
        return self.es.indices.get_mapping(index=self.index_name, doc_type=class_name)

    def reindex(self, obj):

        def convert(data, field):
            if isinstance(data, Literal):
                data = data.value

            if isinstance(data, URIRef):
                return str(data)

            if 'lang' in field.field_type:
                lng = {}
                for d in data:
                    lang = d.language
                    if not lang:
                        lang = 'null'
                    lng[lang] = str(d)
                return lng

            if isinstance(data, list):
                return [convert(x, field) for x in data]

            elif 'date' in field.field_type:
                if isinstance(data, str):
                    data = parse(data)
                return data.strftime('%Y-%m-%dT%H:%M:%S')


            return data

        clz = obj._type[0]
        doc_type = self._get_elastic_class(clz)

        if not issubclass(clz, IndexableFedoraObject):
            # can not reindex something which does not have a mapping
            return

        indexer_data = {}
        for field in clz.indexed_fields:
            data = getattr(obj, field.name)
            if data is None:
                continue

            indexer_data[url2id(field.rdf_name)] = convert(data, field)

        id = base64.b64encode(str(obj.pk).encode('utf-8')).decode('utf-8')

        indexer_data['_fedora_id'] = obj.pk
        indexer_data['_fedora_parent'] = convert(obj[FEDORA.hasParent], FEDORA_PARENT_FIELD)
        indexer_data['_fedoralink_model'] = [
            self._get_elastic_class(x) for x in inspect.getmro(clz)
        ]
        indexer_data['_fedora_type'] = [
            convert(x, FEDORA_TYPE_FIELD) for x in obj[RDF.type]
        ]

        # print(indexer_data)
        try:
            self.es.index(index=self.index_name, doc_type=doc_type, body=indexer_data, id=id)
        except:
            print("Exception in indexing, data", indexer_data)
            traceback.print_exc()


    def _flatten_query(self, q):
        if not is_q(q):
            return
        conn = q.connector
        child_index = -1
        while child_index+1 < len(q.children):
            child_index += 1
            c  = q.children[child_index]

            if is_q(c) and (
                (c.connector == conn and not c.negated) or
                (len(c.children) == 1 and not c.negated)):

                # move children up
                q.children = q.children[:child_index] + c.children + q.children[child_index+1:]
                child_index -= 1
                continue

        for child in q.children:
            self._flatten_query(child)

    def _demorgan(self, q):
        if not is_q(q):
            return
        if q.negated:
            if q.connector == 'AND':
                q.connector = 'OR'
            elif q.connector == 'OR':
                q.connector = 'AND'
            else:
                raise NotImplementedError('demorgan for %s not yet implemented' % q.connector)
            q.negated = False

            for child_index in range(len(q.children)):
                child = q.children[child_index]
                if hasattr(child, 'connector'):
                    child.negated = not child.negated
                    self._demorgan(child)
                else:
                    q.children[child_index] = self._demorgan_primitive(child)
        else:
            for child_index in range(len(q.children)):
                child = q.children[child_index]
                if hasattr(child, 'connector'):
                    self._demorgan(child)

    def _demorgan_primitive(self, val):
        if len(val) == 3:
            return (val[0], val[1], not val[2])
        else:
            return (val[0], val[1], True)

    def _is_filter(self, q):

        if not is_q(q):
            if q[0].endswith('__fulltext'):
                return False
            return True

        for c in q.children:
            if not self._is_filter(c):
                return False

        return True

    def _build_filter(self, q, fld2id, container):
        return self._build_query(q, fld2id, container, False)

    def _build_fulltext(self, q, fld2id, container):
        return self._build_query(q, fld2id, container, True)

    # noinspection PyTypeChecker
    def _build_query(self, q, fld2id, container, inside_fulltext):

        if container is None:
            container = {}

        ret = container

        if not is_q(q):
            self._build_primitive(q, fld2id, container, inside_fulltext_query=inside_fulltext)
            return container

        if q.connector == 'AND':
            container = gc(container, 'bool', {})
            container = gc(container, 'must', [])
        else:
            container = gc(container, 'bool', {})
            container = gc(container, 'should', [])

        by_prefix = {}
        for c in q.children:
            prefix = self._get_common_prefix(c)
            by_prefix.setdefault(tuple(prefix), []).append(c)

        for prefix, children in by_prefix.items():

            if prefix:
                nested = {}
                container.append(nested)
                nested = gc(nested, "nested", {})
                nested['path'] = '.'.join([x for x in map(lambda x: fld2id[x], prefix)])
                nested = gc(nested, 'query', {})

                if q.connector == 'AND':
                    nested = gc(nested, 'bool', {})
                    nested = gc(nested, 'must', [])
                else:
                    nested = gc(nested, 'bool', {})
                    nested = gc(nested, 'should', [])

                cont = nested
            else:
                cont = container

            for c in children:
                r = {}
                cont.append(r)

                self._build_query(c, fld2id, r, inside_fulltext)

        return ret

    def _build_primitive(self, q, fld2id, ret, inside_fulltext_query=True):
        if len(q) == 3:
            if q[2]:
                ret = gc(ret, 'bool', {})
                ret = gc(ret, 'must_not', {})
        prefix, name, oper, transformed_name = self._split_name(q[0], fld2id)

        if not oper or oper == 'exact':
            ret['term'] = {
                transformed_name + "__exact" : q[1]
            }
        elif oper == 'fulltext' and inside_fulltext_query:
            ret['match'] = {
                transformed_name : q[1]
            }
        else:
            raise NotImplementedError("operation %s not yet implemented, inside fulltext match %s" % (oper, inside_fulltext_query))

    def _get_common_prefix(self, q):
        if not is_q(q):
            prefix = self._split_name(q[0], None)[0]
            if not prefix:
                return []
            return prefix.split('.')
        common = None
        for c in q.children:
            prefix = self._get_common_prefix(c)
            if common is None:
                common = prefix
            else:
                if len(common)>len(prefix):
                    common = common[:len(prefix)]
                for i in range(len(common)):
                    if common[i] != prefix[i]:
                        common = common[:i]
                        break
                if not common:
                    break
        return common

    @staticmethod
    def _split_name(name, fld2id):
        name = name.split('__')
        if not name[0]:
            name = name[1:]
            name[0] = '__' + name[0]
        oper = None
        prefix = ''
        if len(name)>1 and name[-1] in ('exact', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith',
                                        'endswith', 'iendswith', 'fulltext', 'gt', 'gte', 'lt', 'lte'):
            oper = name[-1]
            name = name[:-1]
        if len(name) > 1:
            prefix = '.'.join(name[:-1])
        if fld2id:
            if prefix:
                transformed_name = fld2id[prefix] + "." + name[-1]
            else:
                transformed_name = fld2id[name[-1]]
        else:
            transformed_name = None
        name = '.'.join(name)
        # TODO: fedoralink facets

        return prefix, name, oper, transformed_name

    def _get_all_fields(self, q, fields, fld2id):
        if not is_q(q):
            fields.add(self._split_name(q[0], fld2id)[3])
        else:
            for c in q.children:
                self._get_all_fields(c, fields, fld2id)

    def search(self, query, model_class, start, end, facets, ordering, values):

        self._demorgan(query)
        self._flatten_query(query)

        fld2id = {}
        id2fld = {}
        for fld in model_class._meta.fields:
            id_in_elasticsearch = url2id(fld.fedora_field.rdf_name)

            if 'lang' in fld.fedora_field.field_type:
                for lang in settings.LANGUAGES:
                    nested_id_in_elasticsearch = id_in_elasticsearch + '.' + lang[0]

                    fld2id[fld.name + '.' + lang[0]] = nested_id_in_elasticsearch
                    id2fld[nested_id_in_elasticsearch] = fld.name

            fld2id[fld.name] = id_in_elasticsearch
            id2fld[id_in_elasticsearch] = fld.name

        fld2id['_fedoralink_model'] = '_fedoralink_model'
        id2fld['_fedoralink_model'] = '_fedoralink_model'

        all_fields = set()
        self._get_all_fields(query, all_fields, fld2id)

        filters = []
        fulltext_matches  = []

        if query:
            if query.connector != 'AND':
                raise NotImplementedError("Only top-level AND connector is implemented now")

            for c in query.children:
                if self._is_filter(c):
                    filters.append(c)
                else:
                    fulltext_matches.append(c)

            filters.append(Q(_fedoralink_model__exact=self._get_elastic_class(model_class)))

            f = Q()
            f.connector = Q.AND
            f.children = filters
            filters = f

            filters = self._build_filter(filters, fld2id, None)

            f = Q()
            f.connector = Q.AND
            f.children = fulltext_matches
            fulltext_matches = f

            fulltext_matches = self._build_fulltext(fulltext_matches, fld2id, None)
        else:
            filters = Q(_fedoralink_model__exact=self._get_elastic_class(model_class))
            filters = self._build_filter(filters, fld2id, None)
            fulltext_matches = {}

        ordering_clause = []
        if ordering:
            for o in ordering:
                dir = 'asc'
                if o[0] == '-':
                    dir = 'desc'
                    o = o[1:]
                ordering_clause.append({
                    fld2id[o] : {
                        'order': dir
                    }
                })

        facets_clause = {}
        if facets:
            for f in facets:
                facets_clause[fld2id[f.replace('__', '.')]] = {
                    "terms" : {
                        "field": fld2id[f.replace('__', '.')] + "__exact",
                        "size": 0
                    }
                }

        built_query = {}
        if filters:
            built_query['filter'] = {'bool': filters.get('bool', [])}

        if fulltext_matches:
            built_query['query'] = {
                'bool' : fulltext_matches.get('bool', [])
            }
        built_query = {
            "sort": ordering_clause,
            "query": {
                "filtered": built_query
            },
            "aggs" : facets_clause,
            "highlight" : {
                "fields" : {
                    k: {} for k in all_fields
                    # '*' : {}
                },
                 "require_field_match": False
            }
        }

        print(json.dumps(built_query, indent=4))

        resp = self.es.search(body=built_query)

        # print(json.dumps(resp, indent=4))

        instances = []
        for doc in resp['hits']['hits']:
            if values is None:
                instances.append(self.build_instance(doc, model_class, values, id2fld))

        # print(id2fld)

        return {
            'count'  : resp['hits']['total'],
            'data'   : iter(instances),
            'facets' : [
                    (
                        id2fld[k],
                        [ (vv['key'], vv['doc_count']) for vv in v['buckets'] ]
                    ) for k, v in resp.get('aggregations', {}).items()
            ]
        }

    def build_instance(self, doc, model_class, values, id2fld):
        source = doc['_source']
        metadata = RDFMetadata(source['_fedora_id'])

        metadata[FEDORA.hasParent] = URIRef(source['_fedora_parent'])
        metadata[RDF.type] = [URIRef(x) for x in source['_fedora_type']]

        for fld, fldval in source.items():
            if fld in ('_fedora_type', '_fedora_parent', '_fedora_id', '_fedoralink_model'):
                continue

            fld = id2url(fld)
            if isinstance(fldval, dict):
                # TODO: nested !!!
                langs = []
                for lang, val in fldval.items():
                    if lang == 'all':
                        continue
                    if lang == 'null':
                        lang = None
                    langs.append(Literal(val, lang=lang))
            else:
                metadata[URIRef(fld)] = Literal(fldval)

        highlight = { id2fld[k] : v for k, v in doc.get('highlight', {}).items() if k in id2fld }

        return (metadata, highlight)

    def _get_elastic_class(self, model_class):
        return model_class.__module__.replace('.', '_') + "_" + model_class.__name__


def is_q(x):
    return isinstance(x, Q)


if __name__ == '__main__':

    def test():
        import django
        django.setup()

        from fedoralink.common_namespaces.dc import DCObject
        from zaverecne_prace.models import QualificationWork
        from django.db.models import Q

        indexer = ElasticIndexer({
            'SEARCH_URL': 'http://localhost:9200/vscht'
        })

        # resp = QualificationWork.objects.filter(creator__fulltext='Motejlková').order_by('creator').request_facets('department_code')
        # resp = QualificationWork.objects.all().order_by('creator').request_facets('department_code')
        resp = QualificationWork.objects.filter(faculty__cs__fulltext="ochrana").request_facets('faculty__cs')
        print("Facets", resp.facets)
        for o in resp:
            print("Object: ", o, o._highlighted)

        # print(indexer.search(Q(creator__fulltext='Motejlková'), DCObject, None, None, None, None, None))

    test()
