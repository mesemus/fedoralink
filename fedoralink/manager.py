from django.db import connections
from django.db.models.signals import post_save, pre_save

from .utils import TypedStream
from .fedorans import LDP, EBUCORE
from .type_manager import FedoraTypeManager
from .query import LazyFedoraQuery


class FedoraManager:
    """
        An object manager, responsible for:
            1. Creating query sets (via FedoraObject.objects)
            2. Saving objects (via FedoraObject.save, <classmethod>FedoraObject.save_multiple())
    """

    def __init__(self, model_class=None):
        """
        Create a new instance of the manager. The connection used by default is the 'default' configured in settings.py

        :return: Initialized manager
        """
        self._default_connection = None
        self._model_class        = model_class

    def __initialize_connection(self):

        if self._default_connection is None:
            connection = connections['repository']
            connection.connect()

            self._default_connection = connection.connection

    def get_query(self):
        """
        Get a new FedoraQuery

        :return: An initialized LazyFedoraQuery
        """
        return LazyFedoraQuery(self)

    @property
    def connection(self):
        """
        Returns the default connection configured with this manager
        :return: instance of FedoraConnection
        """
        self.__initialize_connection()
        return self._default_connection

    @staticmethod
    def get_manager(model_class=None):
        """
        Returns the default fedora manager for a given object, just now only the base class but will be configurable
        in settings.py

        :return: the default manager if model class is not set, otherwise manager for the given class
        """
        return FedoraManager(model_class)

    @staticmethod
    def get_indexer(using='repository'):
        return connections[using].indexer

    def save(self, objects, connection):
        """
        Saves the objects to the given connection

        :param objects:         the objects to save
        :param connection:      the connection which should be used for saving the object
        :return:                nothing, the objects are updated with the "id" property
        """

        def _serialize_object(object_to_serialize):
            if object_to_serialize.is_incomplete:
                raise AttributeError('Object %s is incomplete, probably obtained from search and can not be saved. ' +
                                     'To get metadata-complete record, call .update() on the object' %
                                     object_to_serialize)
            return {
                'metadata'  : object_to_serialize.metadata,
                'bitstream' : object_to_serialize.get_local_bitstream(),
                'slug'      : object_to_serialize.slug
            }

        objects_to_update = []
        objects_to_create = []

        if connection is None:
            connection = self.connection

        for o in objects:
            if o.objects_fedora_connection == connection and o.id:
                objects_to_update.append(o)
                pre_save.send(sender=o.__class__, instance=o, raw=False, using='repository', update_fields=None)
            else:
                objects_to_create.append(o)
                pre_save.send(sender=o.__class__, instance=o, raw=False, using='repository', update_fields=None)

        if objects_to_update:
            metadata = connection.update_objects([_serialize_object(o) for o in objects_to_update])
            for md, obj in zip(metadata, objects_to_update):
                obj.metadata = md

        if objects_to_create:
            metadata = connection.create_objects([_serialize_object(o) for o in objects_to_create])
            for md, obj in zip(metadata, objects_to_create):
                obj.metadata = md

        for o in objects:
            post_save.send(sender=o.__class__, instance=o, created=None, raw=False, using='repository', update_fields=None)

    def update(self, obj, fetch_child_metadata=True):
        return self.get_query().fetch_child_metadata(fetch_child_metadata).get(pk=obj.id)

    def get_bitstream(self, obj):
        """
        Returns a bitstream associated with the object

        :param obj:     the object
        :return:        TypedStream with object's data
        """

        def get_mimetype(fedora_object):
            ret = fedora_object[EBUCORE.hasMimeType]
            if ret:
                return ret[0].value
            return 'application/binary'

        return TypedStream(self.connection.get_bitstream(obj.id),
                           mimetype=get_mimetype(obj))

    def construct(self, rdf_metadata):
        """
        creates a new instance from RDFMetadata

        :param rdf_metadata:    the metadata
        :return:                instance of the best class(es) which handle the metadata
        """
        clz = FedoraTypeManager.get_object_class(rdf_metadata, self._model_class)
        ret = clz(__metadata=rdf_metadata, __connection=self.connection)

        from fedoralink.models import fedora_object_fetched
        fedora_object_fetched.send(clz, instance=ret, manager=self)

        return ret

    def load_children(self, obj, refetch=True):
        """
        Loads children of the given resource. To make sure that we have actual children, always fetch
        again the object's metadata (do not store them inside the object) and use them to create the
        children

        :param obj:         container to list
        :param refetch:     if set to False, do not refetch
        :return:            list of children
        """
        if refetch:
            meta = list(self.connection.get_object(obj.id))[0]
        else:
            meta = obj.metadata
        children = meta[LDP.contains]
        return [self.construct(meta.clone_for(child)) for child in children]

    def delete(self, obj):
        """
        deletes an object
        :param obj:     object to be deleted
        """
        if obj.id:
            self.connection.delete(obj.id)

    def __getattr__(self, name):
        """
        Whatever attribute is not handled, suppose that it is a query parameter and hand it over to
        LazyQuery. The call to manager.filter(...) is the same as if manager.get_query().filter(...) has been called

        :param name:    name of the method which is being accessed
        :return:        the method
        """
        return getattr(self.get_query(), name)
