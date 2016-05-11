import requests
from django.core.cache import cache

from fedoralink_ui.models import ResourceType, ResourceCollectionType


def simple_cache(func, timeout=3600):
    def wrapper(*args, **kwargs):
        kwargs_sorted = list(kwargs.items())
        kwargs_sorted.sort()
        key = repr(*args) + '##' + repr(kwargs_sorted)
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
    @simple_cache
    def get_template_url(rdf_meta, view_type):
        for rdf_type in rdf_meta:
            retrieved_type = list(ResourceType.objects.filter(rdf_types=rdf_type))
            if retrieved_type:
                break
        else:
            retrieved_type = []

        template_url = None
        for resource_type in retrieved_type:
            if 'type/' in resource_type.id:
                child = FedoraTemplateCache.get_resource_template(resource_type=resource_type, view_type=view_type)
                for template in child.children:
                    template_url = template.id
        return template_url

    @staticmethod
    @simple_cache
    def get_template_string(fedora_object, view_type):
        # noinspection PyProtectedMember
        template_url = FedoraTemplateCache.get_template_url(fedora_object._meta.rdf_types, view_type)
        return requests.get(template_url).text