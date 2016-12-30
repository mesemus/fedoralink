import functools
from django.conf.urls import include, url
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.translation import ugettext_lazy as _

import fedoralink_ui.views
from fedoralink.models import FedoraObject
from django.conf import settings


# TODO: zbavit sa model = DCObject, pridat template pre detail collection (search)


def repository_patterns(app_name, fedora_prefix='', custom_patterns=None):
    urlpatterns = [
        url('^$',
            fedoralink_ui.views.GenericDetailView.as_view(
                fedora_prefix=fedora_prefix), name="index"),
        url(r'^(?P<collection_id>[a-fA-F0-9_/-]*)extended_search(?P<parameters>.*)$',
             fedoralink_ui.views.GenericSearchView.as_view(
                 facets=(),
                 orderings=(
                     ('title@en', _('Sort by title (asc)')),
                     ('-title@en', _('Sort by title (desc)')),
                 ),
                 title='Documents',
                 create_button_title='Create a New Document',
                 fedora_prefix=fedora_prefix),
             name='extended_search'),

        url('^(?P<id>.*)/addSubcollection$', (fedoralink_ui.views.GenericSubcollectionCreateView.as_view(
            fedora_prefix=fedora_prefix,
            success_url="oarepo:detail",
            parent_collection=lambda x: FedoraObject.objects.get(pk=fedora_prefix),
            success_url_param_names=('id',)
        )), name='addSubcollection'),

        url('^(?P<id>.*)/add$', (fedoralink_ui.views.GenericCreateView.as_view(
            fedora_prefix=fedora_prefix,
            success_url="oarepo:detail",
            parent_collection=lambda x: FedoraObject.objects.get(pk=fedora_prefix),
            success_url_param_names=('id',)
        ))
             , name='add'),

        url('^(?P<id>.*)/edit$',
             (fedoralink_ui.views.GenericEditView.as_view(
                 success_url="oarepo:detail",
                 fedora_prefix=fedora_prefix
             )),
             name="edit"),

        url('^(?P<id>.*)$',
            fedoralink_ui.views.GenericDetailView.as_view(
                fedora_prefix=fedora_prefix), name="detail"),
    ]

    if custom_patterns:
        urlpatterns.append(custom_patterns)

    if settings.USE_BREADCRUMBS:
        from autobreadcrumbs.registry import breadcrumbs_registry
        from fedoralink_ui.templatetags.fedoralink_tags import rdf2lang
        import django.utils.translation
        from django.core.cache import cache

        def breadcrumb_detail(request, crumb):
            print(request, crumb.path, crumb.name, crumb.title, crumb.view_args, crumb.view_kwargs)
            id = crumb.view_kwargs['id']
            lang = django.utils.translation.get_language()
            return get_title(id, lang)

        def get_title(id, lang):
            def _get_title():
                try:
                    return rdf2lang(FedoraObject.objects.get(pk=id).title, lang=lang)
                except:
                    import traceback
                    traceback.print_exc()
                    return None

            return cache.get_or_set('title__%s__%s' % (id, lang), _get_title, 3600)

        breadcrumbs_registry.update({
            '%s:detail' % app_name: breadcrumb_detail,
        })

    return [
        url(r'^', include(urlpatterns, namespace=app_name, app_name=app_name))
    ]
