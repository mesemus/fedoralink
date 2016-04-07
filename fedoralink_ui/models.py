from django.db import models
from django.utils.translation import ugettext_lazy as _

# Create your models here.
from fedoralink.fedorans import CESNET_TYPE
from fedoralink.indexer.fields import IndexedTextField, IndexedField, IndexedLinkedField
from fedoralink.indexer.models import IndexableFedoraObject


class TypeCollection(IndexableFedoraObject):

    class Meta:
        rdf_types = (CESNET_TYPE.TypeCollection, )


class Template(IndexableFedoraObject):
    label = IndexedTextField(CESNET_TYPE.label, verbose_name=_('Label'), level=IndexedField.MANDATORY)

    tags = IndexedTextField(CESNET_TYPE.tag, verbose_name=_('Tags'), multi_valued=True)

    def get_template_bitstream(self):
        self.get_bitstream()

    def set_template_bitstream(self, template):
        self.set_local_bitstream(template)

    class Meta:
        rdf_types        = (CESNET_TYPE.Template, )


class Type(IndexableFedoraObject):

    label = IndexedTextField(CESNET_TYPE.label, verbose_name=_('Label'), level=IndexedField.MANDATORY)

    templates_view = IndexedLinkedField(CESNET_TYPE.templates_view, Template, verbose_name=_('Template for view'), multi_valued=True)

    templates_edit = IndexedLinkedField(CESNET_TYPE.templates_edit, Template, verbose_name=_('Template for edit'), multi_valued=True)

    templates_list = IndexedLinkedField(CESNET_TYPE.templates_list, Template, verbose_name=_('Templates for list view'), multi_valued=True)

    controller = IndexedTextField(CESNET_TYPE.controller, verbose_name=_('Controller class'), level=IndexedField.MANDATORY)

    class Meta:
        rdf_types = (CESNET_TYPE.Type, )



class Controller():
    nieco = 'nieco'