import inspect
import logging

import django.dispatch
import rdflib
from io import BytesIO

from django.apps import apps
from rdflib import Literal
from rdflib.namespace import DC, RDF, XSD
from rdflib.term import URIRef

from fedoralink.fedorans import ACL
from .fedorans import FEDORA, EBUCORE
from .manager import FedoraManager
from .rdfmetadata import RDFMetadata
from .type_manager import FedoraTypeManager
from .utils import OrderableModelList

log = logging.getLogger('fedoralink.models')


def get_from_classes(clazz, class_var):
    """
    Get a list of class variables with the given name in clazz and all its superclasses. The values are returned
    in mro order.

    :param clazz:           the class which is being queried
    :param class_var:       class variable name
    :return:                list of values
    """
    ret = []
    for clz in reversed(inspect.getmro(clazz)):
        if hasattr(clz, class_var):
            val = getattr(clz, class_var)
            if isinstance(val, list) or isinstance(val, tuple):
                ret.extend(val)
            else:
                ret.append(val)
    return ret


class Types:
    """
    Helper class which holds RDF types of the object
    """
    def __init__(self, metadata):
        self.__metadata = metadata

    def add(self, a_type):
        self.__metadata.add(RDF.type, a_type)

    def remove(self, a_type):
        self.__metadata.remove(RDF.type, a_type)

    def __iter__(self):
        return iter(self.__metadata[RDF.type])

    def __str__(self):
        return str(list(iter(self)))


class DjangoMetadataBridge:
    """
    A _meta implementation for IndexableFedoraObject
    """
    def __init__(self, model_class, fields):
        self._fields = fields
        self.virtual_fields  = []
        self.concrete_fields = []
        self.many_to_many    = []
        self.verbose_name = getattr(model_class, "verbose_name", model_class.__name__)
        self.model_class = model_class
        process_fields=set()
        for fld in fields:
            if fld.name in process_fields:
                continue
            process_fields.add(fld.name)
            fld.null = not fld.required
            fld.blank = not fld.required
            fld.attname = fld.name
            fld.model = model_class
            self.concrete_fields.append(fld)

        self.fields = self.concrete_fields
        self.fields_by_name = {x.name:x for x in self.fields}
        self.app_label = model_class.__module__
        if self.app_label.endswith('.models'):
            self.app_label = self.app_label[:-7]
        self.object_name = model_class.__name__
        self.apps = apps


class FedoraObjectMetaclass(type):

    def __init__(cls, name, bases, attrs):
        super(FedoraObjectMetaclass, cls).__init__(name, bases, attrs)
        cls.objects = FedoraManager.get_manager(cls)

        cls._meta = DjangoMetadataBridge(cls, [])


class FedoraObject(metaclass=FedoraObjectMetaclass):
    """
    The base class of all Fedora objects, modelled along Django's model

    Most important methods and properties:
        .id
        .children
        .get_bitstream()

        .save()
        .delete()
        .local_bitstream

        .create_child()
        .create_subcollection()

    To get/modify metadata, use [RDF:Name], for example obj[DC.title]. These methods always return a list of metadata.

    """

    def __init__(self, **kwargs):
        self.metadata     = None
        self.__connection = None
        self.__children   = None
        self.__is_incomplete = False

        if '__metadata' in kwargs:
            self.metadata = kwargs['__metadata']
        else:
            self.metadata   = RDFMetadata('')

        if '__connection' in kwargs:
            self.__connection = kwargs['__connection']
        else:
            self.__connection = None

        if '__slug' in kwargs:
            self.__slug = kwargs['__slug']
        else:
            self.__slug = None

        self.types = Types(self.metadata)

        self.__local_bitstream = None

    # objects are filled in by metaclass, this field is here just to make editors happy
    objects = None

    """
        Fields that will be used in indexing (LDPath will be created and installed
        when ./manage.py config_index <modelname> is called)
    """

    @classmethod
    def handles_metadata(cls, _metadata):
        """
        Returns priority with which this class is able to handle the given metadata, -1 or None if not at all

        :type _metadata: RDFMetadata
        :param _metadata: the metadata
        :return:         priority
        """

        # although FedoraObject can handle any fedora object, this is hardcoded into FedoraTypeManager,
        # this method returns None so that subclasses that do not override it will not be mistakenly used in
        # type mapping
        return None

    @property
    def slug(self):
        return self.__slug

    def save(self):
        """
        saves this instance
        """
        getattr(type(self), 'objects').save((self,), None)

    @classmethod
    def save_multiple(cls, objects, connection=None):
        """
        saves multiple instances, might optimize the number of calls to Fedora server
        """
        getattr(cls, 'objects').save(objects, connection)

    @property
    def objects_fedora_connection(self):
        """
        returns the connection which created this object
        """
        return self.__connection

    def get_bitstream(self):
        """
        returns a TypedStream associated with this node
        """
        return self.objects.get_bitstream(self)

    def get_local_bitstream(self):
        """
        returns a local bitstream ready for upload
        :returns TypedStream instance
        """
        return self.__local_bitstream

    def set_local_bitstream(self, local_bitstream):
        """
        sets a local bitstream. Call .save() afterwords to send it to the server
        :param local_bitstream instance of TypedStream
        """
        self.__local_bitstream = local_bitstream

    def created(self):
        pass

    @property
    def children(self):
        return self.list_children()

    def list_children(self, refetch=True):
        return OrderableModelList(get_from_classes(type(self), 'objects')[0].load_children(self, refetch), self)

    def list_self_and_descendants(self):
        stack = [self]
        while len(stack):
            el = stack.pop()
            yield el
            for c in reversed(el.children):
                stack.append(c)

    def create_child(self, child_name, additional_types=None, flavour=None, slug=None):
        child = self._create_child(flavour or FedoraObject, slug)

        if additional_types:
            for t in additional_types:
                child.types.add(t)

        for r in FedoraObject.__convert_name_to_literal(child_name):
            child.metadata.add(DC.title, r)

        child.created()

        return child

    @staticmethod
    def __convert_name_to_literal(child_name):
        rr = []
        if isinstance(child_name, str):
            rr.append(Literal(child_name, datatype=XSD.string))
        elif isinstance(child_name, Literal):
            if child_name.datatype is None:
                child_name = Literal(child_name.value, datatype=XSD.string)
            rr.append(child_name)
        else:
            for c in child_name:
                rr.extend(FedoraObject.__convert_name_to_literal(c))
        return rr

    def create_subcollection(self, collection_name, additional_types=None, flavour=None, slug=None):
        types = [EBUCORE.Collection]
        if additional_types:
            types.extend(additional_types)

        return self.create_child(collection_name, types, flavour=flavour, slug=slug)

    def _create_child(self, child_types, slug):

        if not isinstance(child_types, list):
            child_types = [child_types]

        clz = FedoraTypeManager.generate_class(child_types)

        ret = clz(id=None, __connection=self.__connection, __slug=slug)

        ret[FEDORA.hasParent] = rdflib.URIRef(self.id)

        return ret

    def delete(self):
        getattr(type(self), 'objects').delete(self)

    def update(self, fetch_child_metadata=True):
        """
        Fetches new data from server and overrides this object's metadata with them
        """
        self.metadata = getattr(type(self), 'objects').update(self, fetch_child_metadata).metadata
        self.__is_incomplete = False

    def set_acl(self, acl_collection):
        if isinstance(acl_collection, str):
            acl_collection = FedoraObject.objects.get(pk=acl_collection)
        self[ACL.accessControl] = URIRef(acl_collection.id)

    @property
    def id(self):
        return self.metadata.id

    @property
    def local_id(self):
        connection = self.objects_fedora_connection
        return connection.get_local_id(self.metadata.id)

    @property
    def is_incomplete(self):
        return self.__is_incomplete

    @is_incomplete.setter
    def is_incomplete(self, val):
        self.__is_incomplete = val

    @property
    def fedora_parent_uri(self):
        if FEDORA.hasParent in self.metadata:
            return str(self.metadata[FEDORA.hasParent][0])
        else:
            return None

    def __getitem__(self, item):
        return self.metadata[item]

    def __setitem__(self, key, value):
        self.metadata[key] = value

    def __delitem__(self, key):
        del self.metadata[key]


class UploadedFileStream:

    def __init__(self, file):
        self.file = file
        self.content = BytesIO()
        for c in self.file.chunks():
            self.content.write(c)
        self.content.seek(0)

    def read(self):
        return self.content.read()

    def close(self):
        pass


fedora_object_fetched = django.dispatch.Signal(providing_args=["instance", "manager"])


def get_or_create_object(path, save=False):
    whole_path = '/'.join(map(lambda x: x['slug'] for x in path))
    try:
        obj = FedoraObject.objects.get(whole_path)
        return obj
    except:
        pass
    if len(path) > 1:
        parent = get_or_create_object(path[:-1], True)
    else:
        parent = FedoraObject.objects.get(pk='')
    obj = parent.create_child(child_name=path[-1]['name'],
                              slug=path[-1]['slug'],
                              flavour=path['-1']['flavour'])
    if save:
        obj.save()

    return obj
