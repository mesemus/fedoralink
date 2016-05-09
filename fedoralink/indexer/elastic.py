import inspect
import json
import traceback
import urllib
import urllib.parse

import base64
from dateutil.parser import parse
from django.conf import settings
from django.db.models import Q
from elasticsearch import Elasticsearch
from rdflib import Literal, URIRef, RDF

from fedoralink.fedorans import FEDORA
from fedoralink.indexer import Indexer
from fedoralink.indexer.fields import IndexedTextField, IndexedLanguageField, IndexedDateTimeField, IndexedBinaryField, \
    IndexedLinkedField
from fedoralink.indexer.models import IndexableFedoraObject, fedoralink_classes
from fedoralink.models import FedoraObject
from fedoralink.rdfmetadata import RDFMetadata
from fedoralink.utils import url2id, id2url


class _ITF(IndexedTextField):
    def __init__(self, rdf_name, name):
        super().__init__(rdf_name)
        self.name = name

class _IDF(IndexedDateTimeField):
    def __init__(self, rdf_name, name):
        super().__init__(rdf_name)
        self.name = name

FEDORALINK_TYPE_FIELD = _ITF(FEDORA.fedoralink, name='_fedoralink_model')
FEDORA_TYPE_FIELD = _ITF(RDF.type, name='type')
FEDORA_PARENT_FIELD = _ITF(FEDORA.hasParent, name='parent')
FEDORA_ID_FIELD = _ITF(FEDORA.id, name='id')
FEDORA_CREATED_FIELD = _IDF(FEDORA.created, name='_fedora_created')
FEDORA_LAST_MODIFIED_FIELD = _IDF(FEDORA.lastModified, name='_fedora_last_modified')


class ElasticIndexer(Indexer):
    def __init__(self, repo_conf):
        url = urllib.parse.urlsplit(repo_conf['SEARCH_URL'])
        self.index_name = url.path

        while self.index_name.startswith('/'):
            self.index_name = self.index_name[1:]
        while self.index_name.endswith('/'):
            self.index_name = self.index_name[:-1]

        self.es = Elasticsearch(({"host": url.hostname, "port": url.port},))

        if not self.es.indices.exists(self.index_name):
            self.es.indices.create(index=self.index_name)

    def save_mapping(self, class_name, mapping):
        return self.es.indices.put_mapping(index=self.index_name, doc_type=class_name, body=mapping)

    def get_mapping(self, class_name):
        return self.es.indices.get_mapping(index=self.index_name, doc_type=class_name)

    def reindex(self, obj):

        # get the fedoralink's original class from the obj.
        clz = fedoralink_classes(obj)[0]

        if not issubclass(clz, IndexableFedoraObject):
            # can not reindex something which does not have a mapping
            return

        doc_type = self._get_elastic_class(clz)

        indexer_data = {}
        for field in clz._meta.fields:
            data = getattr(obj, field.name)
            if data is None:
                continue

            converted_value = convert(data, field)
            indexer_data[url2id(field.rdf_name)] = converted_value

        encoded_fedora_id = base64.b64encode(str(obj.pk).encode('utf-8')).decode('utf-8')

        indexer_data['_fedora_id'] = obj.pk
        indexer_data['_fedora_parent'] = convert(obj[FEDORA.hasParent], FEDORA_PARENT_FIELD)
        indexer_data['_fedoralink_model'] = [ self._get_elastic_class(x) for x in inspect.getmro(clz) ]
        indexer_data['_fedora_type'] = [ convert(x, FEDORA_TYPE_FIELD) for x in obj[RDF.type] ]
        indexer_data['_fedora_created'] = [ convert(x, FEDORA_CREATED_FIELD) for x in obj[FEDORA.created] ]
        indexer_data['_fedora_last_modified'] = [ convert(x, FEDORA_LAST_MODIFIED_FIELD) for x in obj[FEDORA.lastModified] ]

        # noinspection PyBroadException
        try:
            self.es.index(index=self.index_name, doc_type=doc_type, body=indexer_data, id=encoded_fedora_id)
        except:
            print("Exception in indexing, data", indexer_data)
            traceback.print_exc()
        print("reindexing single object ok")

    def _flatten_query(self, q):
        if not is_q(q):
            return
        conn = q.connector
        child_index = -1
        while child_index + 1 < len(q.children):
            child_index += 1
            c = q.children[child_index]

            if is_q(c) and ((c.connector == conn and not c.negated) or (len(c.children) == 1 and not c.negated)):
                # move children up
                q.children = q.children[:child_index] + c.children + q.children[child_index + 1:]
                child_index -= 1
                continue

        for child in q.children:
            self._flatten_query(child)

    def _de_morgan(self, q):
        if not is_q(q):
            return
        if q.negated:
            if q.connector == 'AND':
                q.connector = 'OR'
            elif q.connector == 'OR':
                q.connector = 'AND'
            else:
                raise NotImplementedError('de morgan for %s not yet implemented' % q.connector)
            q.negated = False

            for child_index in range(len(q.children)):
                child = q.children[child_index]
                if hasattr(child, 'connector'):
                    child.negated = not child.negated
                    self._de_morgan(child)
                else:
                    q.children[child_index] = self._de_morgan_primitive(child)
        else:
            for child_index in range(len(q.children)):
                child = q.children[child_index]
                if hasattr(child, 'connector'):
                    self._de_morgan(child)

    @staticmethod
    def _de_morgan_primitive(val):
        if len(val) == 3:
            return val[0], val[1], not val[2]
        else:
            return val[0], val[1], True

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
            container = container.setdefault('bool', {})
            container = container.setdefault('must', [])
        else:
            container = container.setdefault('bool', {})
            container = container.setdefault('should', [])

        by_prefix = {}
        for c in q.children:
            prefix = self._get_common_prefix(c)
            by_prefix.setdefault(tuple(prefix), []).append(c)

        for prefix, children in by_prefix.items():

            if prefix:
                nested = {}
                container.append(nested)
                nested = nested.setdefault("nested", {})
                nested['path'] = '.'.join([x for x in map(lambda x: fld2id[x], prefix)])
                nested = nested.setdefault('query', {})

                if q.connector == 'AND':
                    nested = nested.setdefault('bool', {})
                    nested = nested.setdefault('must', [])
                else:
                    nested = nested.setdefault('bool', {})
                    nested = nested.setdefault('should', [])

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
                ret = ret.setdefault('bool', {})
                ret = ret.setdefault('must_not', {})
        prefix, name, comparison_operation, transformed_name = self._split_name(q[0], fld2id)

        if not comparison_operation or comparison_operation == 'exact':
            ret['term'] = {
                transformed_name + "__exact": q[1]
            }
        elif comparison_operation == 'fulltext' and inside_fulltext_query:
            ret['match'] = {
                transformed_name: q[1]
            }
        else:
            raise NotImplementedError("operation %s not yet implemented, inside fulltext match %s" %
                                      (comparison_operation, inside_fulltext_query))

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
                if len(common) > len(prefix):
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
        comparison_operation = None
        prefix = ''
        if len(name) > 1 and name[-1] in ('exact', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith',
                                          'endswith', 'iendswith', 'fulltext', 'gt', 'gte', 'lt', 'lte'):
            comparison_operation = name[-1]
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

        return prefix, name, comparison_operation, transformed_name

    def _get_all_fields(self, q, fields, fld2id):
        if not q:
            return
        if not is_q(q):
            fields.add(self._split_name(q[0], fld2id)[3])
        else:
            for c in q.children:
                self._get_all_fields(c, fields, fld2id)

    # noinspection PyProtectedMember
    def search(self, query, model_class, start, end, facets, ordering, values):
        self._de_morgan(query)
        self._flatten_query(query)

        fld2id = {}
        id2fld = {}
        for fld in model_class._meta.fields:
            id_in_elasticsearch = url2id(fld.rdf_name)

            if isinstance(fld, IndexedLanguageField):
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
        fulltext_matches = []

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

        ordering_clause = self._generate_ordering_clause(fld2id, ordering)

        facets_clause = self._generate_facet_clause(facets, fld2id)

        built_query = {}
        if filters:
            built_query['filter'] = {'bool': filters.get('bool', [])}

        if fulltext_matches:
            built_query['query'] = {
                'bool': fulltext_matches.get('bool', [])
            }

        built_query = {
            "sort": ordering_clause,
            "query": {
                "filtered": built_query
            },
            "aggs": facets_clause,
            "highlight": {
                "fields": {
                    k: {} for k in all_fields
                    # '*' : {}
                },
                "require_field_match": False
            },
            "from": start if start else 0,
            "size": (end - start) if start and end else 10
        }

        print(json.dumps(built_query, indent=4))

        resp = self.es.search(body=built_query)

        # print(json.dumps(resp, indent=4))

        instances = []
        for doc in resp['hits']['hits']:
            if values is None:
                instances.append(self.build_instance(doc, id2fld))

        facets = []
        for k, v in resp.get('aggregations', {}).items():
            if 'buckets' in v:
                # normal value
                buckets = v['buckets']
            else:
                # nested value, always called "value" - defined above
                buckets = v['value']['buckets']

            facets.append((
                id2fld[k],
                [(vv['key'], vv['doc_count']) for vv in buckets]
            ))

        return {
            'count': resp['hits']['total'],
            'data': iter(instances),
            'facets': facets
        }

    @staticmethod
    def _generate_facet_clause(facets, fld2id):
        facets_clause = {}
        if facets:
            for f in facets:
                field_in_elastic = fld2id[f.replace('__', '.')]
                if '__' in f:
                    li = f.rfind('__')
                    path = fld2id[f[:li].replace('__', '.')]
                    facets_clause[field_in_elastic] = {
                        "nested": {
                            "path": path
                        },
                        "aggs": {
                            "value": {
                                "terms": {
                                    "field": field_in_elastic + "__exact",
                                    "size": 0
                                }
                            }
                        }
                    }
                else:
                    facets_clause[field_in_elastic] = {
                        "terms": {
                            "field": field_in_elastic + "__exact",
                            "size": 0
                        }
                    }
        return facets_clause

    @staticmethod
    def _generate_ordering_clause(fld2id, ordering):
        ordering_clause = []
        if ordering:
            for o in ordering:
                sort_direction = 'asc'
                if o[0] == '-':
                    sort_direction = 'desc'
                    o = o[1:]
                o = o.replace('@', '.')        # replace blah@cs with blah.cs
                if o in ('_fedora_created', '_fedora_last_modified'):
                    ordering_clause.append({
                        o: {
                            'order': sort_direction
                        }
                    })
                else:
                    ordering_clause.append({
                        fld2id[o] + "__exact": {
                            'order': sort_direction
                        }
                    })
        return ordering_clause

    @staticmethod
    def build_instance(doc, id2fld):
        source = doc['_source']
        metadata = RDFMetadata(source['_fedora_id'])

        metadata.rdf_metadata.set((metadata.id, FEDORA.hasParent, URIRef(source['_fedora_parent'])))
        for x in source['_fedora_type']:
            metadata.rdf_metadata.set((metadata.id, RDF.type, URIRef(x)))

        for fld, field_value in source.items():
            if fld in ('_fedora_type', '_fedora_parent', '_fedora_id', '_fedoralink_model', '_fedora_created', '_fedora_last_modified'):
                continue

            fld = id2url(fld)
            if isinstance(field_value, dict):
                # TODO: nested !!!
                languages = []
                for lang, val in field_value.items():
                    if lang == 'all':
                        continue
                    if lang == 'null':
                        lang = None
                    metadata.rdf_metadata.set((metadata.id, URIRef(fld), Literal(val, lang=lang)))
            elif isinstance(field_value, list) or isinstance(field_value, tuple):
                for val in field_value:
                    metadata.rdf_metadata.set((metadata.id, URIRef(fld), Literal(val)))
            else:
                metadata.rdf_metadata.set((metadata.id, URIRef(fld), Literal(field_value)))

        highlight = {id2fld[k]: v for k, v in doc.get('highlight', {}).items() if k in id2fld}

        return metadata, highlight

    @staticmethod
    def _get_elastic_class(model_class):
        return model_class.__module__.replace('.', '_') + "_" + model_class.__name__


def is_q(x):
    return isinstance(x, Q)


def convert(data, field):
    if isinstance(data, Literal):
        data = data.value

    if isinstance(data, URIRef):
        return str(data)

    if isinstance(field, IndexedLanguageField):
        lng = {}
        for d in data:
            lang = d.language
            if not lang:
                lang = 'null'
            lng[lang] = str(d)
        return lng

    if isinstance(data, list):
        return [x for x in [convert(x, field) for x in data] if x]

    elif isinstance(field, IndexedDateTimeField):
        if data is None:
            return None
        if isinstance(data, str):
            data = parse(data)
        return data.strftime('%Y-%m-%dT%H:%M:%S')

    elif data and isinstance(data, FedoraObject):
        return data.id

    return data


if __name__ == '__main__':

    def test():
        import django
        django.setup()

        # noinspection PyUnresolvedReferences
        from zaverecne_prace.models import QualificationWork
        from django.db.models import Q

        # resp = QualificationWork.objects.filter(creator__fulltext='Motejlková').
        #                                  order_by('creator').request_facets('department_code')
        # resp = QualificationWork.objects.all().order_by('creator').request_facets('department_code')
        resp = QualificationWork.objects.filter(faculty__cs__fulltext="ochrana").request_facets('faculty__cs',
                                                                                                'faculty_code')
        print("Facets", resp.facets)
        for o in resp:
            # noinspection PyProtectedMember
            print("Object: ", o, o._highlighted)

        # indexer = ElasticIndexer({
        #     'SEARCH_URL': 'http://localhost:9200/vscht'
        # })
        #
        # print(indexer.search(Q(creator__fulltext='Motejlková'), DCObject, None, None, None, None, None))


    test()
