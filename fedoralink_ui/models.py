from django.db import models
from django.utils.translation import ugettext_lazy as _

# Create your models here.
from fedoralink.fedorans import CESNET_TYPE
from fedoralink.indexer.fields import IndexedTextField, IndexedField, IndexedLinkedField
from fedoralink.indexer.models import IndexableFedoraObject


class ResourceTypeCollection(IndexableFedoraObject):
    class Meta:
        rdf_types = (CESNET_TYPE.ResourceTypeCollection,)


class Template(IndexableFedoraObject):
    label = IndexedTextField(CESNET_TYPE.label, verbose_name=_('Label'), level=IndexedField.MANDATORY)

    tags = IndexedTextField(CESNET_TYPE.tag, verbose_name=_('Tags'), multi_valued=True)

    class Meta:
        rdf_types = (CESNET_TYPE.Template,)


class ResourceType(IndexableFedoraObject):
    label = IndexedTextField(CESNET_TYPE.label, verbose_name=_('Label'), level=IndexedField.MANDATORY)

    template_view = IndexedLinkedField(CESNET_TYPE.template_view, Template, verbose_name=_('Template for view'))

    template_edit = IndexedLinkedField(CESNET_TYPE.template_edit, Template, verbose_name=_('Template for edit'))

    template_list_item = IndexedLinkedField(CESNET_TYPE.template_list_item, Template,
                                            verbose_name=_('Template for item list view'))

    controller = IndexedTextField(CESNET_TYPE.controller, verbose_name=_('Controller class'),
                                  level=IndexedField.MANDATORY)

    rdf_types = IndexedTextField(CESNET_TYPE.rdf_types, verbose_name=_('RDF types'), level=IndexedField.MANDATORY,
                                 multi_valued=True)

    fedoralink_model = IndexedTextField(CESNET_TYPE.fedoralink_model, verbose_name=_('Fedoralink model class name'),
                                        level=IndexedField.MANDATORY)

    class Meta:
        rdf_types = (CESNET_TYPE.ResourceType,)


class ResourceFieldType(IndexableFedoraObject):
    label = IndexedTextField(CESNET_TYPE.label, verbose_name=_('Label'), level=IndexedField.MANDATORY)

    resource_types = IndexedLinkedField(CESNET_TYPE.resource_types, ResourceType,
                                        verbose_name=_('Containing resource types'),
                                        multi_valued=True)

    field_name = IndexedTextField(CESNET_TYPE.field_name, verbose_name=_('Field name'))

    field_fedoralink_type = IndexedTextField(CESNET_TYPE.field_fedoralink_type,
                                             verbose_name=_('Field fedoralink type, for example IndexedTextField'))

    template_field_detail_view = IndexedLinkedField(CESNET_TYPE.template_field_detail_view, Template,
                                                    verbose_name=_('Template for field inside detail view'))

    class Meta:
        rdf_types = (CESNET_TYPE.ResourceFieldType,)


class ResourceCollectionType(ResourceType):
    
    template_search = IndexedLinkedField(CESNET_TYPE.template_search, Template,
                                         verbose_name=_('Templates for list/search view'), multi_valued=True)

    primary_child_type = IndexedLinkedField(CESNET_TYPE.primary_child_type, ResourceType,
                                            verbose_name=_('Primary collection\'s child type, '
                                                           'used for example for search or resource creation'))

    class Meta:
        rdf_types = (CESNET_TYPE.ResourceCollectionType,)


class Controller():
    nieco = 'nieco'
