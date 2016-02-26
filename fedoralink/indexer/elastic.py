import json
import traceback
import urllib
import urllib.parse

import base64
import functools
from django.db.models import Q

import fedoralink
from dateutil.parser import parse
from elasticsearch import Elasticsearch
from rdflib import Literal, URIRef, RDF

from fedoralink.fedorans import FEDORA
from fedoralink.indexer import Indexer, IndexedField, FEDORA_TYPE_FIELD, FEDORA_PARENT_FIELD
from fedoralink.models import IndexableFedoraObject

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
                indexer_data[field.name] = str(data)

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
        doc_type = clz.__module__.replace('.', '_') + "_" + clz.__name__

        if not issubclass(clz, IndexableFedoraObject):
            # can not reindex something which does not have a mapping
            return

        indexer_data = {}
        for field in clz.indexed_fields:
            data = getattr(obj, field.name)
            if data is None:
                continue

            indexer_data[field.name] = convert(data, field)

        id = base64.b64encode(str(obj.pk).encode('utf-8')).decode('utf-8')

        indexer_data['__fedora__id'] = obj.pk
        indexer_data['__fedora__parent'] = convert(obj[FEDORA.hasParent], FEDORA_PARENT_FIELD)
        indexer_data['__fedora__type'] = convert(obj[RDF.type], FEDORA_TYPE_FIELD)

        # print(indexer_data)
        try:
            self.es.index(index=self.index_name, doc_type=doc_type, body=indexer_data, id=id)
        except:
            print("Exception in indexing, data", indexer_data)
            traceback.print_exc()

    def _transform_q(self, query, ret):
        if query.negated:
            if 'not' not in ret:
                ret['not'] = {}
            ret = ret['not']

        if query.connector == 'AND':
            if 'bool' not in ret:
                ret['bool'] = {}
            ret = ret['bool']
            if 'must' not in ret:
                ret['must'] = []
            ret = ret['must']
        else:
            if 'should' not in ret:
                ret['should'] = []
            ret = ret['should']

        for c in query.children:
            rr = {}
            ret.append(rr)
            self._build_query(c, rr)


    def _transform_primitive(self, query, ret):
        name, value = query
        name = name.split('__')

        if len(name)>1 and name[-1] in ('exact', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith',
                                        'endswith', 'iendswith', 'fulltext', 'gt', 'gte', 'lt', 'lte'):
            oper = name[-1]
            name = name[:-1]
        else:
            oper = 'fulltext'

        name = '.'.join(name)

        exact = False
        if oper == 'exact':
            exact = True
            if 'filtered' not in ret:
                ret['filtered'] = {}
            ret = ret['filtered']
            if 'filter' not in ret:
                ret['filter'] = []
            ret = ret['filter']

            term = {}
            ret.append(term)
            ret = term

            ret['term'] = {}
            ret = ret['term']

            ret[name] = value

        elif oper == 'startswith':
            if 'prefix' not in ret:
                ret['prefix'] = {}
            ret = ret['prefix']
            raise NotImplementedError("Operator %s is not yet implemented in elasticsearch bridge")
        elif oper == 'fulltext':
            if 'match' not in ret:
                ret['match'] = {}
            ret = ret['match']
            if name not in ret:
                ret[name] = {}
            ret = ret[name]

            if 'query' not in ret:
                ret['query'] = []
            ret = ret['query']

            ret.append(value)
        else:
            raise NotImplementedError("Operator %s is not yet implemented in elasticsearch bridge")


    def _build_query(self, query, ret):

        if query is None:
            ret["match_all"] = {}
            return

        if hasattr(query, 'connector'):
            self._transform_q(query, ret)
        else:
            # primitive value
            self._transform_primitive(query, ret)

    def _flatten_query(self, q):
        if not hasattr(q, 'connector'):
            return
        conn = q.connector
        child_index = -1
        while child_index+1 < len(q.children):
            child_index += 1
            c  = q.children[child_index]

            if (getattr(c, 'connector', None) == conn and not c.negated) or \
                    (len(getattr(c, 'children', [])) == 1 and not c.negated):
                # move children up
                q.children = q.children[:child_index] + c.children + q.children[child_index+1:]
                child_index -= 1
                continue

        for child in q.children:
            self._flatten_query(child)

    def _demorgan(self, q):
        print(q)
        if not hasattr(q, 'connector'):
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

        if not hasattr(q, 'children'):
            if q[0].endswith('__fulltext'):
                return False
            return True

        for c in q.children:
            if not self._is_filter(c):
                return False

        return True

    # noinspection PyTypeChecker
    def _build_filter(self, q, container=None):

        if container is None:
            container = {}

        ret = container

        if not hasattr(q, 'children'):
            self._build_filter_primitive(q, container)
            return container

        if q.connector == 'AND':
            container = gc(container, 'bool', {})
            container = gc(container, 'must', [])
        else:
            container = gc(container, 'bool', {})
            container = gc(container, 'should', [])

        for c in q.children:
            r = {}
            container.append(r)
            self._build_filter(c, r)

        return ret


    def _build_filter_primitive(self, q, ret):
        if len(q) == 3:
            if q[2]:
                ret = gc(ret, 'bool', {})
                ret = gc(ret, 'must_not', {})
        prefix, name, oper = self._split_name(q[0])
        if prefix:
            raise NotImplementedError("nested not yet implemented")
        else:
            if not oper or oper == 'exact':
                ret['term'] = {
                    name + "__exact" : q[1]
                }
            else:
                raise NotImplementedError("operation %s not yet implemented" % oper)


    # noinspection PyTypeChecker
    def _build_fulltext(self, q, container=None):

        if container is None:
            container = {}

        ret = container

        if not hasattr(q, 'children'):
            self._build_fulltext_primitive(q, container)
            return container

        if q.connector == 'AND':
            container = gc(container, 'bool', {})
            container = gc(container, 'must', [])
        else:
            container = gc(container, 'bool', {})
            container = gc(container, 'should', [])

        for c in q.children:
            r = {}
            container.append(r)
            self._build_fulltext(c, r)

        return ret


    def _build_fulltext_primitive(self, q, ret):
        if len(q) == 3:
            if q[2]:
                ret = gc(ret, 'bool', {})
                ret = gc(ret, 'must_not', {})
        prefix, name, oper = self._split_name(q[0])
        if prefix:
            raise NotImplementedError("nested not yet implemented")
        else:
            if not oper or oper == 'exact':
                ret['term'] = {
                    name + "__exact" : q[1]
                }
            elif oper=='fulltext':
                ret['match'] = {
                    name : q[1]
                }
            else:
                raise NotImplementedError("operation %s not yet implemented" % oper)


    def _split_name(self, name):
        name = name.split('__')
        oper = None
        prefix = None
        if len(name)>1 and name[-1] in ('exact', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith',
                                        'endswith', 'iendswith', 'fulltext', 'gt', 'gte', 'lt', 'lte'):
            oper = name[-1]
            name = name[:-1]
        if len(name)>1:
            prefix = '.'.join(name[:-1])
        name = '.'.join(name)
        return prefix, name, oper



    def search(self, query, model_class, start, end, facets, ordering, values):

        self._demorgan(query)
        self._flatten_query(query)

        print(query)

        if query.connector != 'AND':
            raise NotImplementedError("Only top-level AND connector is implemented now")

        filters = []
        fulltext_matches  = []

        for c in query.children:
            if self._is_filter(c):
                filters.append(c)
            else:
                fulltext_matches.append(c)

        print("Filters", filters)
        print("Fulltext matches", fulltext_matches)

        f = Q()
        f.connector = Q.AND
        f.children = filters
        filters = f

        filters = self._build_filter(filters)

        f = Q()
        f.connector = Q.AND
        f.children = fulltext_matches
        fulltext_matches = f

        fulltext_matches = self._build_fulltext(fulltext_matches)


        built_query = {
            "query": {
                "filtered": {
                    "filter": {
                        'bool' : filters['bool']
                    },
                    "query": {
                        'bool' : fulltext_matches['bool']
                    }
                }
            }
        }

        print(json.dumps(built_query, indent=4))


if __name__ == '__main__':

    def test():

        from fedoralink.models import FedoraObject
        from django.db.models import Q

        indexer = ElasticIndexer({
            'SEARCH_URL': 'http://localhost:9200/vscht'
        })
        indexer.search(Q(faculty_code__exact='FCHI')&~Q(title__fulltext='Kinetika'), FedoraObject, None, None, None, None, None)

    test()