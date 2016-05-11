import requests
from django.core.cache import cache

from fedoralink_ui.models import ResourceType


def simple_cache(func, timeout=3600):
    def wrapper(*args, **kwargs):
        kwargs_sorted = list(kwargs.items())
        kwargs_sorted.sort()
        key = repr(args) + '##' + repr(kwargs_sorted)
        ret = cache.get(key, None)
        if ret:
            return ret
        ret = func(*args, **kwargs)
        cache.set(key, ret, timeout=timeout)
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
        return None

    @staticmethod
    def get_template_object(rdf_meta, view_type):
        for rdf_type in rdf_meta:
            retrieved_type = list(ResourceType.objects.filter(rdf_types__exact=rdf_type))
            if retrieved_type:
                break
        else:
            retrieved_type = []

        for resource_type in retrieved_type:
            child = FedoraTemplateCache.get_resource_template(resource_type=resource_type, view_type=view_type)
            if child:
                return child
        return None

    @staticmethod
    def get_template_string(fedora_object, view_type):
        # noinspection PyProtectedMember
        rdf_types = fedora_object._meta.rdf_types
        return FedoraTemplateCache._get_template_string_internal(rdf_types, view_type)

    @staticmethod
    @simple_cache
    def _get_template_string_internal(rdf_types, view_type):
        template_object = FedoraTemplateCache.get_template_object(rdf_types, view_type)
        if template_object is not None and template_object.get_bitstream() is not None:
            return template_object.get_bitstream().stream.read().decode("utf-8")
        return None
