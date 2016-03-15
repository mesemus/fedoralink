import logging
import rdflib
import rdflib.term
from .sparql import SparqlSerializer
from io import BytesIO

from .fedorans import NAMESPACES, RDF, FEDORA

log = logging.getLogger('fedoralink.rdfmetadata')


class RDFMetadata:
    """
    Represents a rdf:Description within a rdf:RDF
    """

    def __init__(self, self_id, metadata=None):
        """
        the metadata element might contains descriptions about more elements than this.
         self_id is used to filter out the triplets with subject=self_id

        :param self_id:     will look for rdf:about with this id
        :param metadata:    instance of rdflib.Graph
        """
        self.__id = rdflib.term.URIRef(self_id)

        if metadata is None:
            metadata = rdflib.Graph()
        else:
            if not len(list(metadata[self.__id])):
                if self_id.endswith('/'):
                    test_id = self_id[:-1]
                else:
                    test_id = self_id + '/'
                test_id = rdflib.term.URIRef(test_id)

                if len(list(metadata[test_id])):
                    self.__id = test_id
                else:
                    log.warning('Strange thing happened - REST call did not return metadata for %s', self.id)

        for k, v in NAMESPACES.items():
            metadata.bind(k, rdflib.URIRef(v), override=False)

        self.__metadata = metadata

        self.__added_triplets    = {}
        self.__removed_triplets  = {}

    @property
    def id(self):
        """
        Identifier (URL) of resource that has these metadata
        """
        return self.__id

    def set_id(self, id):
        """
        Change the identifier to a new value; This means that all triplets with the original id as subject will
        change to the new id.

        :param id: the new id
        """
        id = rdflib.term.URIRef(id)
        for p, o in self.__metadata[self.__id]:
            # change the subject of the triplet
            self.__metadata.remove((self.__id, p, o))
            self.__metadata.add((id, p, o))
        self.__id = id

    def add(self, predicate, value):
        """
        Add a new predicate to the metadata. Subject is always the 'id' attribute of this resource

        :param predicate:   the predicate
        :param value:       the value, must be rdflib.URIRef or rdflib.Literal
        """
        self.__add_to_metadata_only(predicate, value)
        if predicate not in self.__added_triplets:
            self.__added_triplets[predicate] = []
        self.__added_triplets[predicate].append(value)

    def __add_to_metadata_only(self, predicate, value):
        self.__metadata.add((self.__id, predicate, value))

    def add_type(self, a_type):
        """
        Add a new RDF:type

        :param a_type: instance of rdflib.URIRef
        """
        self.add(RDF.type, a_type)

    def clone_for(self, uri):
        """
        Extract all triplets with subject equal to the given uri and return instance
        of RDFMetadata(uri, selected_triplets)

        :param uri: uri to search for in subjects
        :return:    new RDFMetadata
        """
        uriref = rdflib.term.URIRef(uri)
        ret = RDFMetadata(uri, None) # TODO: add metadata from self
        for fact in self.__metadata[uriref:]:
            ret.__add_to_metadata_only(*fact)
        # the parent uri is not present, so add it ...
        ret.add(FEDORA.hasParent, self.id)
        return ret

    def has_type(self, a_type):
        """
        Checks if this metadata contain the given rdf type
        :param a_type: rdflib.URIRef with the type
        :return: True if the metadata contain the type
        """
        types = self.__metadata.objects(self.__id, RDF.type)
        for t in types:
            if a_type == t:
                return True
        return False

    def __getitem__(self, predicate):
        """
        Get metadata.
        :param predicate:        the predicate
        :return:                list of values (either rdflib.URIRef or rdflib.Literal)
        """

        if not isinstance(predicate, rdflib.term.URIRef):
            raise TypeError('Predicate must be an instance of URiRef')

        return list(self.__metadata.objects(self.__id, predicate))

    def __setitem__(self, predicate, value):
        """
        Sets metadata
        :param predicate:       the predicate
        :param value:           list of values or a single value. If not rdflib.URIRef or rdflib.Literal,
                                conversion to Literal is performed.
        """
        if not isinstance(predicate, rdflib.term.URIRef):
            raise TypeError('Predicate must be an instance of URiRef')

        if not isinstance(value, list) and not isinstance(value, tuple):
            value = [value]

        for it in value:
            if isinstance(it, rdflib.Literal):
                if it.datatype is None and it.language is None:
                    raise Exception("Expected datatype on literal %s" % it)
            elif not isinstance(it, rdflib.URIRef):
                raise Exception("Expected only Literal or URIRef or a list of these types")

        self.__delete_predicate(predicate,set(value))
        existing_values = set(self[predicate])
        added = []
        for v in value:
            if v not in existing_values:
                self.__metadata.add((self.__id, predicate, v))
                added.append(v)
        if added:
            self.__added_triplets[predicate] = added

    def __delitem__(self, predicate):
        self.__delete_predicate(predicate)

    def __delete_predicate(self, predicate, ignored_values = None):
        removed = []
        if ignored_values is None:
            ignored_values = set()
        for val in self[predicate]:
            if val not in ignored_values:
                removed.append(val)
                self.__metadata.remove((self.__id, predicate, val))
        if predicate not in self.__removed_triplets:
            self.__removed_triplets[predicate] = removed
        if predicate in self.__added_triplets:
            self.__added_triplets[predicate]=[x for x in self.__added_triplets[predicate] if x not in ignored_values]
            if not self.__added_triplets[predicate]:
                del self.__added_triplets[predicate]

    def __contains__(self, predicate):
        return len(self[predicate]) > 0        # TODO: optimize this

    def __str__(self):
        return self.__metadata.serialize(format='turtle').decode('utf-8')

    def serialize_sparql(self):
        stream = BytesIO()
        serializer = SparqlSerializer(self.__metadata, self.__removed_triplets, self.__added_triplets)
        serializer.serialize(stream)
        return stream.getvalue()


    @property
    def rdf_metadata(self):
        return self.__metadata


