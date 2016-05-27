from django.core.cache import cache
from django.db.models import Q

from fedoralink.utils import fullname
from fedoralink_ui.models import ResourceType, ResourceFieldType, ResourceCollectionType

NONE_CACHE_VALUE = "this is a placeholder that is used instead of None"

def simple_cache(func, timeout=3600):
    def wrapper(*args, **kwargs):
        kwargs_sorted = list(kwargs.items())
        kwargs_sorted.sort()
        key = repr(args) + '##' + repr(kwargs_sorted)
        print("cache key:")
        print(key)
        ret = cache.get(key, None)
        if not ret:
            ret = func(*args, **kwargs)
            if not ret:
                ret = NONE_CACHE_VALUE
            cache.set(key, ret, timeout=timeout)
        if ret == NONE_CACHE_VALUE:
            ret = None
        return ret

    return wrapper


class FedoraTemplateCache:

    @staticmethod
    def get_resource_template(resource_type, view_type):
        # TODO: more templates
        if view_type == 'edit' or view_type == 'create':
            return resource_type.template_edit
        if view_type == 'view':
            return resource_type.template_view
        if view_type == 'search':
            return resource_type.template_search
        if view_type == 'search_row':
            return resource_type.template_list_item
        return None

    @staticmethod
    def get_template_object(rdf_meta, view_type):
        retrieved_type = FedoraTemplateCache.get_resource_type(rdf_meta)
        if retrieved_type:
            return FedoraTemplateCache.get_resource_template(resource_type=retrieved_type, view_type=view_type)
        return None

    @staticmethod
    def get_resource_type(rdf_meta):
        for rdf_type in rdf_meta:
            retrieved_type = list(ResourceType.objects.filter(rdf_types__exact=rdf_type))
            if retrieved_type:
                return retrieved_type[0]
        return None

    @staticmethod
    def get_collection_resource_type(rdf_meta):
        for rdf_type in rdf_meta:
            retrieved_type = list(ResourceCollectionType.objects.filter(rdf_types__exact=rdf_type))
            if retrieved_type:
                return retrieved_type[0]
        return None

    @staticmethod
    def get_collection_model(fedora_collection):
        # noinspection PyProtectedMember
        if hasattr(fedora_collection, '_meta'):
            rdf_types = fedora_collection._meta.rdf_types
            return FedoraTemplateCache._get_collection_model_internal(rdf_types)
        else:
            return 'fedoralink.common_namespaces.dc.DCObject'

    @staticmethod
    @simple_cache
    def _get_collection_model_internal(rdf_types):
        collection_resource_type = FedoraTemplateCache.get_collection_resource_type(rdf_types)
        if not collection_resource_type:
            return 'fedoralink.common_namespaces.dc.DCObject'
        primary_child_type = collection_resource_type.primary_child_type
        if not primary_child_type:
            return None#'fedoralink.common_namespaces.dc.DCObject'
        model_name = primary_child_type.fedoralink_model
        if not model_name:
            return None#'fedoralink.common_namespaces.dc.DCObject'
        return str(model_name)

    @staticmethod
    def get_subcollection_model(fedora_collection):
        # noinspection PyProtectedMember
        if hasattr(fedora_collection, '_meta'):
            rdf_types = fedora_collection._meta.rdf_types
            return FedoraTemplateCache._get_subcollection_model_internal(rdf_types)
        else:
            return 'fedoralink.common_namespaces.dc.DCObject'

    @staticmethod
    @simple_cache
    def _get_subcollection_model_internal(rdf_types):
        collection_resource_type = FedoraTemplateCache.get_collection_resource_type(rdf_types)
        if not collection_resource_type:
            return 'fedoralink.common_namespaces.dc.DCObject'
        primary_subcollection_type = collection_resource_type.primary_subcollection_type
        if not primary_subcollection_type:
            return None#'fedoralink.common_namespaces.dc.DCObject'
        model_name = primary_subcollection_type.fedoralink_model
        if not model_name:
            return None#'fedoralink.common_namespaces.dc.DCObject'
        return str(model_name)

    @staticmethod
    def get_template_string(fedora_object, view_type):
        # noinspection PyProtectedMember
        if hasattr(fedora_object, '_meta'):
            rdf_types = fedora_object._meta.rdf_types
            return FedoraTemplateCache._get_template_string_internal(rdf_types, view_type)
        else:
            return None

    @staticmethod
    @simple_cache
    def _get_template_string_internal(rdf_types, view_type):
        return FedoraTemplateCache._load_template(FedoraTemplateCache.get_template_object(rdf_types, view_type))

    @staticmethod
    def _load_template(template_object):
        if template_object is not None and template_object.get_bitstream() is not None:
            return template_object.get_bitstream().stream.read().decode("utf-8")
        return None

    @staticmethod
    def get_field_template_string(fedora_object, field_name):
        if hasattr(fedora_object, '_meta'):
            field_fedoralink_type = fullname(fedora_object._meta.fields_by_name[field_name].__class__)

            # noinspection PyProtectedMember
            rdf_types = fedora_object._meta.rdf_types
            return FedoraTemplateCache._get_field_template_string_internal(field_name, rdf_types, field_fedoralink_type)
        else:
            return None

    @staticmethod
    @simple_cache
    def _get_field_template_string_internal(field_name, rdf_types, field_fedoralink_type):
        print(locals())
        retrieved_type = FedoraTemplateCache.get_resource_type(rdf_types)
        query = FedoraTemplateCache.get_query(field_fedoralink_type, field_name, retrieved_type)
        retrieved_field_types = list(ResourceFieldType.objects.filter(query))
        if not retrieved_field_types:
            return None

        def sort_field_types(retrieved_field_type):
            value = 4 if retrieved_field_type.resource_type == retrieved_type else 0
            value += 2 if retrieved_field_type.field_name == field_name else 0
            value += 1 if retrieved_field_type.field_fedoralink_type == field_fedoralink_type else 0
            return -value

        retrieved_field_types.sort(key=sort_field_types)
        return FedoraTemplateCache._load_template(retrieved_field_types[0].template_field_detail_view)

    @staticmethod
    def get_query(field_fedoralink_type, field_name, retrieved_type):
        query = Q(field_name__exact=field_name, field_fedoralink_type__exact=field_fedoralink_type, resource_type__exact=None)
        query |= Q(field_name__exact=None, field_fedoralink_type__exact=field_fedoralink_type, resource_type__exact=None)
        query |= Q(field_name__exact=field_name, field_fedoralink_type__exact=None, resource_type__exact=None)
        if retrieved_type is not None:
            query |= Q(field_name__exact=field_name, field_fedoralink_type__exact=field_fedoralink_type, resource_type__exact=retrieved_type.id)
            query |= Q(field_name__exact=None, field_fedoralink_type__exact=field_fedoralink_type, resource_type__exact=retrieved_type.id)
            query |= Q(field_name__exact=field_name, field_fedoralink_type__exact=None, resource_type__exact=retrieved_type.id)
        return query
