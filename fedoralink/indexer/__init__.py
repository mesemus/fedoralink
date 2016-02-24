import logging

from fedoralink.fedorans import RDF, FEDORA

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
    def xml_schema_type(self):
        return 'xsd:string'
        #
        # # TODO: differentiating does not seem to work, fedora stores all as string even if created as Literal?
        #
        # if 'text' in self.field_type:
        #     return 'xsd:string'
        # if 'binary' in self.field_type:
        #     return 'xsd:string'
        # if 'string' in self.field_type:
        #     return 'xsd:string'
        # if 'lang_text' in self.field_type:  # multilang text is also xsd:string
        #     return 'xsd:string'
        # if 'date' in self.field_type:
        #     return 'xsd:dateTime'
        # if 'int' in self.field_type:
        #     return 'xsd:int'
        # log.error('Undefined xml schema type for type(s) %s', self.field_type)
        # return 'xsd:string'

    @property
    def split_rdf_name(self):
        r = self.rdf_name
        if '#' in r:
            return r.split('#')
        idx = r.rfind('/') + 1
        return r[:idx], r[idx:]

    def __str__(self):
        return "%s" % self.rdf_name

    def __repr__(self):
        return str(self)

FEDORA_TYPE_FIELD = IndexedField('type', RDF.type)
FEDORA_PARENT_FIELD = IndexedField('parent', FEDORA.hasParent)
FEDORA_ID_FIELD = IndexedField('id', FEDORA.id)


class Indexer:
    # abstract method
    def search(self, query, model_class, start, end, facets, ordering, values):
        raise Exception("Please reimplement this method in inherited classes")