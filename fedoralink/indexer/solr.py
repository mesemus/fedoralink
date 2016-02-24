import json
import logging
from urllib.error import HTTPError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

import re
import requests
from django.conf import settings
from django.db import connections
from rdflib import Literal, URIRef

from fedoralink.fedorans import FEDORA_INDEX
from fedoralink.indexer import Indexer
from fedoralink.rdfmetadata import RDFMetadata

log = logging.getLogger('fedoralink.indexer')


TEXT = {'text'}
STRING = {'string'}
MULTI_LANG = {'lang'}
MULTI_VAL = {'multi'}
DATE = {'date'}
INT  = {'int'}
BINARY = {'binary'}

class IndexedField:

    def __init__(self, property_name, rdf_name, indexed=True, stored=True, type=TEXT, prefix='',
                 verbose_name=None, required=False):
        self.name       = property_name
        self.rdf_name   = rdf_name
        self.indexed    = indexed
        self.stored     = stored
        self.field_type = type
        self.prefix     = prefix
        self.verbose_name = verbose_name if verbose_name is not None else self.name
        self.required   = required

    def __hash__(self):
        return hash(self.rdf_name)

    def __eq__(self, other):
        return self.rdf_name == other.rdf_name

    def combine(self, other):
        """
        Combines this field and another one with the same name. The indexed, stored properties are logically or-ed.

        :param other: the other instance of the same IndexedField
        :return: a newly created indexed field
        """

        return IndexedField(self.name, self.rdf_name,
                            self.indexed  or other.indexed,
                            self.stored or other.stored,
                            self.field_type,
                            self.prefix)

    @property
    def indexer_name(self):
        postfix = '_'

        if 'text' in self.field_type:
            postfix += 't'

        if self.stored:
            postfix += 's'

        return self.prefix + self.name + postfix

    @property
    def xml_schema_type(self):
        return 'xsd:string'

        # TODO: differentiating does not seem to work, fedora stores all as string even if created as Literal?

        if 'text' in self.field_type:
            return 'xsd:string'
        if 'binary' in self.field_type:
            return 'xsd:string'
        if 'string' in self.field_type:
            return 'xsd:string'
        if 'lang_text' in self.field_type:  # multilang text is also xsd:string
            return 'xsd:string'
        if 'date' in self.field_type:
            return 'xsd:dateTime'
        if 'int' in self.field_type:
            return 'xsd:int'
        log.error('Undefined xml schema type for type(s) %s', self.field_type)
        return 'xsd:string'

    @property
    def split_rdf_name(self):
        r = self.rdf_name
        if '#' in r:
            return r.split('#')
        idx = r.rfind('/') + 1
        return r[:idx], r[idx:]

    def __str__(self):
        return "%s <=> %s" % (self.rdf_name, self.indexer_name)

MAX_PAGE_SIZE = 100


class SOLRIndexer(Indexer):

    def __init__(self, solr_url):
        self.solr_url = solr_url

    def install_indexed_field(self, field):
        if not field.indexed:
            return
        payload = {
            'add-field': {
                'name': field.indexer_name,
                'type' : 'text',
                'stored' : field.stored
            }
        }
        try:
            url = self.solr_url + '/schema'
            log.info('Installing field %s (url %s)', field.indexer_name, url)
            req = Request(url, data=json.dumps(payload).encode('utf-8'), method='POST')
            req.add_header('Content-Type', 'application/json')
            resp = urlopen(req)
        except HTTPError as e:
            log.error('Error installing field %s: %s', field.indexer_name, e.fp.read())

    def _build_query(self, query, mapper, ret):
        if query is None:
            ret.append('*:*')
            return

        if hasattr(query, 'connector'):
            self._transform_q(query, mapper, ret)
        else:
            # primitive value
            ret.append(self._transform_primitive(query, mapper))

    def _transform_q(self, query, mapper, ret):
        ret.append('(')
        op = False
        if query.negated:
            ret.append('-(')
        for c in query.children:
            if op:
                ret.append(' %s ' % ('&&' if query.connector == 'AND' else '||'))
            else:
                op = True
            self._build_query(c, mapper, ret)
        if query.negated:
            ret.append(')')
        ret.append(')')

    def _transform_primitive(self, query, mapper):
        name, value = query
        name = name.split('__')

        if name[0] == 'solr_all_fields':
            tname = 'solr_all_fields_t'
        else:
            tname = mapper.field_to_search(name[0])

        if len(name) == 1:
            # return direct query
            if self.is_string(mapper, name) and tname.endswith('_ts'):
                return '%s:"%s"' % (tname, self._escape('^^^^%s$$$$' % value))
            else:
                return '%s:"%s"' % (tname, self._escape(value))

        if len(name) > 2:
            raise AttributeError('links in Q are not supported yet (and probably will never be)')

        if name[1] == 'contains' or name[1] == 'icontains':
            return '%s:"%s"' % (tname, self._escape(value))

        if name[1] == 'startswith' or name[1] == 'istartswith':
            if self.is_string(mapper, name):
                return '%s:"%s"' % (tname, self._escape('^^^^%s' % value))
            else:
                raise AttributeError('__startswith works only for strings')

        if name[1] == 'endswith' or name[1] == 'iendswith':
            if self.is_string(mapper, name):
                return '%s:"%s"' % (tname, self._escape('%s$$$$' % value))
            else:
                raise AttributeError('__startswith works only for strings')

        if name[1] == 'fulltext':
            return '%s:%s' % (tname, self._escape('%s' % value))

        raise AttributeError('Operator __%s not yet supported' % name[1])

    def is_string(self, mapper, name):

        if name[0] == 'solr_all_fields':
            return True

        return mapper.is_string(name[0])

    def _escape(self, s):
        return re.sub(r'([+&|!(){}[]^"~*?:/\-])', r'\$1', s)

    def search(self, query, model, start, end, facets, ordering, values):
        mapper = self.get_search_mapper(model)
        qs = []
        self._build_query(query, mapper, qs)
        qs = ''.join(qs)
        if mapper.model:
            fq = '(fedora_mixin_types_t:"%s")' % self._escape("%s" % mapper.model.__name__)
        else:
            fq = '*:*'

        facet_q = ''
        solr_facets = set()
        if facets:
            facet_q = '&facet=true'
            for facet in facets:
                solr_facet = mapper.field_to_search(facet)
                solr_facets.add(solr_facet)
                facet_q += '&facet.field=' + quote(solr_facet)

        if end is not None:
            rows = end - start
        else:
            rows = MAX_PAGE_SIZE

        sort = []
        if ordering:
            for o in ordering:

                if o.startswith('-'):
                    direction = 'desc'
                    o = o[1:]
                else:
                    direction = 'asc'

                field_name = mapper.field_to_search(o)
                if field_name.endswith('_ts'):
                    field_name = 'sort__%s_s' % field_name[:-3]

                sort.append('%s %s' % (field_name, direction))

        values_q = ''
        if values is not None:
            # only return id + these values
            values_q += '&fl=id'
            for val in values:
                values_q += ',' + quote(mapper.field_to_search(val))

        # call solr
        url = self.solr_url + "/select?" + urlencode({
            'q' : qs,
            'fq' : fq,
            'wt': 'json',
            'indent': 'true',
            'start' : start,
            'rows' : rows,
            'sort' : ','.join(sort),
            'hl': 'true',
            'hl.fl': '*',
            'hl.requireFieldMatch' : 'true'
        }) + facet_q + values_q

        log.info('Calling SOLR, url %s', url)

        req = Request(url)
        data = urlopen(req).read().decode('utf-8')
        resp = json.loads(data)

        data = []

        for doc in resp['response']['docs']:
            metadata = RDFMetadata(doc['id'])
            fields = {}
            for k, v in doc.items():
                if k in ('id', '_version_', 'solr_all_fields_t', 'fedora_mixin_types_t', 'fedora_parent_id_t'):
                    if k == 'id' and values is not None:
                        fields['id'] = [URIRef(v)]

                    continue

                if k.startswith('sort__'):
                    continue # ignore sort fields

                key, language = mapper.search_to_rdf(k)
                if values is not None:
                    key, language = mapper.search_to_field(k)


                if key not in fields:
                    fields[key] = []

                if isinstance(v, str):
                    v = v.replace('^^^^', '').replace('$$$$', '')
                    if v.strip() == '':
                        continue

                if language:
                    fields[key].append(Literal(v, lang=language))
                else:
                    fields[key].append(Literal(v))

            if values is None:
                for field_name, field_values in fields.items():
                    try:
                        # language has already been taken care of
                        metadata[field_name] = field_values
                    except AttributeError:
                        log.error('Could not map key %s to target class. Unknown language or schema error?' % field_name)

                data.append((metadata,
                             {mapper.search_to_field(k) : v
                                    for k, v in resp.get('highlighting', {}).get(doc['id'], {}).items()
                                                if k not in solr_facets
                              }))
            else:
                data.append(fields)

        returned_facets = [
                (
                    concat_lang(mapper.search_to_field(solr_name)),
                    [
                        (val, count) for val, count in zip(values[::2], values[1::2])
                    ]
                )
                for solr_name, values in resp.get('facet_counts', {}).get('facet_fields', {}).items()
            ]

        returned_facets.sort(key=lambda x: facets.index(x[0]))

        return {
            'count': resp['response']['numFound'],
            'data' : iter(data),
            'facets' : returned_facets
        }

    # noinspection PyMethodMayBeStatic
    def reindex(self, obj):
        try:
            try:
                transformation = str(obj[FEDORA_INDEX.hasIndexingTransformation][0])
            except Exception as e:
                return

            # call with the indexing transform:  url/fcr:transform/<transformation_name>
            url = "%s/fcr:transform/%s" % (obj.id, transformation)

            connection = connections['repository']

            try:
                content = connection.connection.raw_get(url)
            except HTTPError as e:
                log.error('Error calling transformation on %s: %s', obj.id, e)
                return

            solr_url = settings.DATABASES['repository']['SEARCH_URL'] + "/update?commit=true"

            log.warn('Vyresit autentikaci pro solr ... v metode reindex tridy SOLRIndexer')
            resp = requests.post(solr_url, data=content, headers={
                'Content-Type': 'application/json'
            })
            if resp.status_code // 100 != 2:
                log.error("Error updating %s: %s", obj.id, resp.content)
        except:
            import traceback
            traceback.print_exc()

    def get_search_mapper(self, model):
        if model:
            return ModelSearchMapper(model)
        else:
            return IdentitySearchMapper()


def concat_lang(x):
    if x[1]:
        return x[0] + '@' + x[1]
    else:
        return x[0]

def parse_language(key):
    from django.conf import settings

    for lang in settings.LANGUAGES:
        if key.startswith(lang[0] + "__"):
            return key[len(lang) + 2:], lang[0]
    return key, None



# noinspection PyMethodMayBeStatic
class IdentitySearchMapper:

    def field_to_search(self, fld):
        return fld

    def search_to_rdf(self, searchfld):
        return searchfld

    # noinspection PyUnusedLocal
    def is_string(self, fld):
        # don't know ...
        return False


class ModelSearchMapper:
    def __init__(self, model):
        if not hasattr(model, 'indexed_fields'):
            raise Exception('Only instances of IndexableFedoraObject could be used in search')
        self.model = model

    def is_string(self, fld):
        if '@' in fld:                  # if there is language in field name, strip it out
            fld = fld.split('@')[0]
        for afld in self.model.indexed_fields:
            if afld.name == fld:
                return afld.xml_schema_type == 'xsd:string'
        raise AttributeError('Field %s not found in searchable fields of class %s' % (fld, self.model))

    def field_to_search(self, fld):
        lang = ''
        if '@' in fld:                  # if there is language in field name, strip it out
            fld, lang = fld.split('@')
            lang += '__'

        for afld in self.model.indexed_fields:
            if afld.name == fld:
                return lang + afld.indexer_name

        raise AttributeError('Field %s not found in searchable fields of class %s' % (fld, self.model))

    def search_to_rdf(self, searchfld):
        lang = None
        if searchfld[2:4] == '__':
            lang = searchfld[:2]
            searchfld = searchfld[4:]

        for afld in self.model.indexed_fields:
            if afld.indexer_name == searchfld:
                return afld.rdf_name, lang
        raise AttributeError('Indexer field %s not found in searchable fields of class %s' % (searchfld, self.model))

    def search_to_field(self, searchfld):

        if searchfld == 'solr_all_fields_t':
            return 'solr_all_fields'

        lang = None
        if searchfld[2:4] == '__':
            lang = searchfld[:2]
            searchfld = searchfld[4:]

        for afld in self.model.indexed_fields:
            if afld.indexer_name == searchfld:
                return afld.name, lang

        raise AttributeError('Indexer field %s not found in searchable fields of class %s' % (searchfld, self.model))
