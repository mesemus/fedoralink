import datetime
import inspect
import traceback

import inflection as inflection
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db.models.signals import class_prepared
from rdflib import Literal

from fedoralink.fedorans import FEDORA_INDEX
from fedoralink.fields import DjangoMetadataBridge
from fedoralink.indexer.fields import IndexedField, IndexedLanguageField, IndexedDateField, IndexedIntegerField
from fedoralink.models import FedoraObjectMetaclass, FedoraObject
from fedoralink.type_manager import FedoraTypeManager
from fedoralink.utils import StringLikeList, TypedStream


class IndexableFedoraObjectMetaclass(FedoraObjectMetaclass):

    @staticmethod
    def all_indexed_fields(cls):
        vars = set()
        for clazz in reversed(inspect.getmro(cls)):
            # un-metaclassed class has fields directly
            flds = list(inspect.getmembers(clazz, lambda x: isinstance(x, IndexedField)))
            flds.sort(key=lambda x: x[1].order)
            for name, fld in flds:
                if name not in vars:
                    vars.add(name)
                    fld.name = name
                    fld.editable = True
                    yield fld

            # after metaclass, the fields are turned into properties, the original fields are in _meta
            clazz_meta = getattr(clazz, '_meta', None)
            if clazz_meta:
                for fld in clazz_meta.fields:
                    if not fld.name: raise Exception('Name not set, wrong implementation !')
                    if fld.name not in vars:
                        vars.add(fld.name)
                        fld.editable = True
                        yield fld

    @staticmethod
    def fill_rdf_types(cls):
        rdf_types = set()
        for clazz in inspect.getmro(cls):
            clazz_meta = getattr(clazz, '_meta', None)
            if clazz_meta:
                for rt in getattr(clazz_meta, 'rdf_types', []):
                    rdf_types.add(rt)
            clazz_meta = getattr(clazz, 'Meta', None)
            if clazz_meta:
                for rt in getattr(clazz_meta, 'rdf_types', []):
                    rdf_types.add(rt)
        return tuple(rdf_types)

    def __init__(cls, name, bases, attrs):
        super(IndexableFedoraObjectMetaclass, cls).__init__(name, list(bases), attrs)

        def create_property(prop):

            def _convert_from_rdf(data):
                if isinstance(prop, IndexedDateField):
                    if data.value:
                        if isinstance(data.value, datetime.datetime):
                            return data.value
                        if data.value=="None": #TODO:  neskor odstranit
                            return None
                        try:
                            # handle 2005-06-08 00:00:00+00:00
                            val = data.value
                            if val[-3] == ':':
                                val = val[:-3] + val[-2:]
                            val = datetime.datetime.strptime(val, '%Y-%m-%d %H:%M:%S%z')
                            return val
                        except:
                            traceback.print_exc()
                            pass

                        raise AttributeError("Conversion of %s [%s] to datetime is not supported in "
                                             "fedoralink/indexer/models.py" % (type(data.value), data.value))

                if isinstance(prop, IndexedIntegerField):
                    return data.value

                return data

            def _convert_to_rdf(data):
                if isinstance(prop, IndexedDateField):
                    if data:
                        if isinstance(data, datetime.datetime):
                            return Literal(data)
                        raise AttributeError("Conversion of %s to datetime is not supported in "
                                             "fedoralink/indexer/models.py" % type(data))

                if isinstance(prop, IndexedIntegerField):
                    return Literal(data)

                return Literal(data)

            def getter(self):
                if not isinstance(prop, IndexedLanguageField) and not prop.multi_valued:
                    # simple type -> return the first item only

                    ret = self.metadata[prop.rdf_name]
                    if len(ret):
                        return _convert_from_rdf(ret[0])
                    else:
                        return None

                return StringLikeList([_convert_from_rdf(x) for x in self.metadata[prop.rdf_name]])

            def setter(self, value):
                collected_streams = __get_streams(value)
                if len(collected_streams) > 0:
                    if not hasattr(self, '__streams'):
                        setattr(self, '__streams', {})
                    streams = getattr(self, '__streams')
                    streams[prop] = collected_streams
                else:
                    if isinstance(value, list) or isinstance(value, tuple):
                        value = [_convert_to_rdf(x) for x in value]
                    else:
                        value = _convert_to_rdf(value)

                    self.metadata[prop.rdf_name] = value

            def __get_streams(value):
                streams = []
                if isinstance(value, tuple) or isinstance(value, list):
                    for x in value:
                        rr = __get_streams(x)
                        streams.extend(rr)
                elif isinstance(value, UploadedFile) or isinstance(value, TypedStream):
                    streams.append(value)
                return streams

            return property(getter, setter)

        indexed_fields = tuple(IndexableFedoraObjectMetaclass.all_indexed_fields(cls))
        for p in indexed_fields:
            setattr(cls, p.name, create_property(p))

        # store django _meta
        cls._meta = DjangoMetadataBridge(cls, indexed_fields)

        cls._meta.rdf_types = IndexableFedoraObjectMetaclass.fill_rdf_types(cls)

        if cls._meta.rdf_types and not cls.__name__.endswith('_bound'):
            FedoraTypeManager.register_model(cls, on_rdf_type=cls._meta.rdf_types)

        class_prepared.send(sender=cls)



class IndexableFedoraObject(FedoraObject, metaclass=IndexableFedoraObjectMetaclass):
    def created(self):
        super().created()
        self.types.add(FEDORA_INDEX.Indexable)
        for rdf_type in self._meta.rdf_types:
            self.types.add(rdf_type)

        self[FEDORA_INDEX.hasIndexingTransformation] = Literal(self.get_indexer_transform())

    def get_indexer_transform(self):
        return inflection.underscore(type(self).__name__.replace('_bound', ''))

    def full_clean(self, exclude=[], validate_unique=False):
        errors = {}
        for fld in self._meta.fields:
            if fld.required:
                if not getattr(self, fld.name):
                    errors[fld.name] = "Field %s is required" % fld.name

        if errors:
            raise ValidationError(errors)

    def validate_unique(self, exclude=[]):
        pass

    @property
    def pk(self):
        return self.id


def fedoralink_classes(obj):
    """
    Get the original fedoralink classes of of a given object. They might be different to real classes (via getmro) because
    fedoralink autogenerates types when deserializing from RDF metadata/Indexer data.

    :param obj: an instance of FedoraObject
    :return:    list of classes
    """
    # noinspection PyProtectedMember
    return obj._type


def fedoralink_streams(obj):
    """
    Return an iterator of tuples (field, instance of TypedStream or UploadedFile)
    that were registered (via setting an instance of these classes
    to any property) with the object.

    :param obj: an instance of FedoraObject
    :return:    iterator of tuples
    """
    return getattr(obj, '__streams', {}).items()


def fedoralink_clear_streams(obj):
    """
    Removes registered streams from an instance of FedoraObject

    :param obj: instance of FedoraObject
    """
    setattr(obj, '__streams', {})