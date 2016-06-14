# import inspect
#
# from django.core.urlresolvers import resolve, reverse
#
# import fedoralink.views
#
# from django.conf.urls import url, include, patterns
# from django.utils.translation import ugettext_lazy as _
#
#
# def get_view(view_or_class, **kwargs):
#     if inspect.isclass(view_or_class):
#         return view_or_class.as_view(**kwargs)
#     else:
#         return view_or_class
#
#
# def repository_patterns(app_name, model, index=fedoralink.views.GenericIndexView,
#                         extended_search=fedoralink.views.GenericIndexerView,
#                         link=fedoralink.views.GenericLinkView,
#                         link_title=fedoralink.views.GenericLinkTitleView,
#                         add=fedoralink.views.GenericDocumentCreate, detail=fedoralink.views.GenericDetailView,
#                         download=fedoralink.views.GenericDownloadView, edit=fedoralink.views.GenericEditView,
#                         change_state=fedoralink.views.GenericChangeStateView,
#                         search_base_template='baseOArepo/search_base.html',
#                         search_list_item_template='baseOArepo/repo_fragments/list/dokument.html',
#                         link_base_template='baseOArepo/link_base.html',
#                         link_list_item_template='baseOArepo/repo_fragments/list/dokument.html',
#                         link_title_template='baseOArepo/link_title.html',
#                         search_facets=(),
#                         search_orderings=(
#                                 ('title@en', _('Sort by title (asc)')),
#                                 ('-title@en', _('Sort by title (desc)')),
#                         ),
#                         search_default_ordering='title@en',
#                         add_template_name='baseOArepo/create.html',
#                         add_parent_collection=None, add_success_url='detail', add_success_url_param_names=('pk',),
#                         detail_template_name='baseOArepo/detail.html', detail_prefix="",
#                         edit_template_name='baseOArepo/edit.html', edit_success_url='detail', edit_prefix="",
#                         edit_success_url_param_names=('pk',),
#                         attachment_model=None,
#                         labels = {},
#                         custom_patterns=None):
#
#     fedoralink.views.ModelViewRegistry.register_view(model, 'link', app_name, 'link')
#     fedoralink.views.ModelViewRegistry.register_view(model, 'link_title', app_name, 'link_title')
#     fedoralink.views.ModelViewRegistry.register_view(model, 'search', app_name, 'rozsirene_hledani')
#     fedoralink.views.ModelViewRegistry.register_view(model, 'add', app_name, 'add')
#     fedoralink.views.ModelViewRegistry.register_view(model, 'download', app_name, 'download')
#     fedoralink.views.ModelViewRegistry.register_view(model, 'edit', app_name, 'edit')
#     fedoralink.views.ModelViewRegistry.register_view(model, 'detail', app_name, 'detail')
#
#     pat = [
#         url(r'^$', get_view(index, app_name=app_name), name="index"),
#         #    breadcrumb=_('dcterms:index')),
#
#         url(r'^extended_search(?P<parametry>.*)$',
#             get_view(extended_search, model=model, base_template=search_base_template,
#                      list_item_template=search_list_item_template, facets=search_facets,
#                      orderings=search_orderings,
#                      default_ordering=search_default_ordering,
#                      title=labels.get('search_title', 'Documents'),
#                      create_button_title=labels.get('create_button_title', 'Create a New Document')),
#             name='rozsirene_hledani'),
#         #    breadcrumb=_('Rozšířené hledání')),
#
#         url(r'^link-title/(?P<pk>[^/]+)$',
#             get_view(link_title, model=model, template_name=link_title_template, prefix=detail_prefix),
#             name='link_title'),
#         #    breadcrumb=_('Rozšířené hledání')),
#
#         url(r'^link(?P<parametry>.*)$',
#             get_view(link, model=model, base_template=link_base_template,
#                      list_item_template=link_list_item_template, facets=search_facets,
#                      orderings=search_orderings,
#                      default_ordering=search_default_ordering,
#                      title=labels.get('search_title', 'Documents')),
#             name='link'),
#         #    breadcrumb=_('Rozšířené hledání')),
#
#         url('^add/(?P<pk>[^/]+)*$', get_view(add, model=model, template_name=add_template_name,
#                               success_url=app_name + ":" + add_success_url,
#                               success_url_param_names=add_success_url_param_names,
#                               parent_collection=add_parent_collection,
#                               title=labels.get('create_title', 'Create Document'))
#            , name='add'),
#         #     breadcrumb=_('Přidání akreditace')),
#         #
#         url('^download/(?P<bitstream_id>[0-9a-z_-]+)$',
#             get_view(download, model=attachment_model), name="download"),
#         #     breadcrumb=_('dcterms:download')),
#         url('^edit/(?P<pk>[^/]+)$',
#             get_view(edit, model=model, template_name=edit_template_name,
#                      success_url=app_name + ":" + edit_success_url,
#                      success_url_param_names=edit_success_url_param_names,
#                      prefix=edit_prefix, title=labels.get('edit_title', 'Edit Document')),
#             name="edit"),
#
#         url('^change_state/(?P<pk>[^/]+)$',
#             get_view(change_state), name="change_state"),
#
#         url('^(?P<pk>[^/]+)$',
#             get_view(detail, template_name=detail_template_name,
#                      prefix=detail_prefix), name="detail"),
#     ]
#
#     if custom_patterns:
#         pat.append(custom_patterns)
#
#     return [
#         url(r'^', include(patterns('',
#                                    *pat
#                                    ), namespace=app_name))
#     ]
#
# def appname(request):
#     return {'appname': resolve(request.path).namespace}

from django.conf.urls import url, include, patterns

import fedoralink_ui.views
from urlbreadcrumbs import url as burl
from django.utils.translation import ugettext_lazy as _

from fedoralink.common_namespaces.dc import DCObject
from fedoralink.models import FedoraObject


# TODO: zbavit sa model = DCObject, pridat template pre detail collection (search)
def repository_patterns(app_name, fedora_prefix='', custom_patterns=None):
    urlpatterns = [
        url('^$',
            fedoralink_ui.views.GenericDetailView.as_view(
                fedora_prefix=fedora_prefix), name="index"),
        burl(r'^(?P<collection_id>[a-fA-F0-9_/-]*)extended_search(?P<parameters>.*)$',
             fedoralink_ui.views.GenericSearchView.as_view(
                 facets=(),
                 orderings=(
                     ('title@en', _('Sort by title (asc)')),
                     ('-title@en', _('Sort by title (desc)')),
                 ),
                 title='Documents',
                 create_button_title='Create a New Document',
                 fedora_prefix=fedora_prefix),
             name='extended_search', verbose_name=_('DCterms')),

        burl('^(?P<pk>.*)/addSubcollection$', fedoralink_ui.views.GenericSubcollectionCreateView.as_view(
            fedora_prefix=fedora_prefix,
            success_url="dcterms:detail",
            parent_collection=lambda x: FedoraObject.objects.get(pk=fedora_prefix),
            success_url_param_names=('id',)
        ), name='addSubcollection'),

        burl('^(?P<pk>.*)/add$', fedoralink_ui.views.GenericCreateView.as_view(
            fedora_prefix=fedora_prefix,
            success_url="dcterms:detail",
            parent_collection=lambda x: FedoraObject.objects.get(pk=fedora_prefix),
            success_url_param_names=('id',)
        )
             , name='add'),

        burl('^(?P<id>.*)/edit$',
             fedoralink_ui.views.GenericEditView.as_view(
                 success_url="dcterms:detail",
                 fedora_prefix=fedora_prefix
             ),
             name="edit"),

        url('^(?P<id>.*)$',
            fedoralink_ui.views.GenericDetailView.as_view(
                fedora_prefix=fedora_prefix), name="detail"),
    ]

    if custom_patterns:
        urlpatterns.append(custom_patterns)

    return [
        burl(r'^', include(patterns('',
                                   *urlpatterns
                                   ), namespace=app_name, app_name=app_name))
    ]

urlpatterns = repository_patterns(app_name="oarepo")#, fedora_prefix="dcterms")