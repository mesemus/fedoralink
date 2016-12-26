from django.conf.urls import include, patterns
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.translation import ugettext_lazy as _

import fedoralink_ui.views
from fedoralink.models import FedoraObject
from urlbreadcrumbs import url as burl


# TODO: zbavit sa model = DCObject, pridat template pre detail collection (search)
def repository_patterns(app_name, fedora_prefix='', custom_patterns=None):
    urlpatterns = [
        burl('^$',
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
             name='extended_search', verbose_name=_('Search')),

        burl('^(?P<id>.*)/addSubcollection$', (fedoralink_ui.views.GenericSubcollectionCreateView.as_view(
            fedora_prefix=fedora_prefix,
            success_url="oarepo:detail",
            parent_collection=lambda x: FedoraObject.objects.get(pk=fedora_prefix),
            success_url_param_names=('id',)
        )), name='addSubcollection'),

        burl('^(?P<id>.*)/add$', (fedoralink_ui.views.GenericCreateView.as_view(
            fedora_prefix=fedora_prefix,
            success_url="oarepo:detail",
            parent_collection=lambda x: FedoraObject.objects.get(pk=fedora_prefix),
            success_url_param_names=('id',)
        ))
             , name='add'),

        burl('^(?P<id>.*)/edit$',
             (fedoralink_ui.views.GenericEditView.as_view(
                 success_url="oarepo:detail",
                 fedora_prefix=fedora_prefix
             )),
             name="edit"),

        burl('^(?P<id>.*)$',
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
