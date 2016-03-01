from rdflib.namespace import DC
from django.utils.translation import ugettext_lazy as _

from fedoralink.indexer.fields import IndexedMultiLangField, IndexedTextField, IndexedDateField
from fedoralink.models import IndexableFedoraObject
from fedoralink.type_manager import FedoraTypeManager


#
# DCObject is indexable and provides .title and .creator property, that get mapped to
# DC.* predicates in RDF by simple_namespace_mapper
#
class DCObject(IndexableFedoraObject):

    title         = IndexedMultiLangField(DC.title, required=True,
                                          verbose_name=_('Title (dublin core)'),
                                          attrs={'presentation': 'textarea'})

    alternative   = IndexedTextField(DC.alternative, required=True,
                                     verbose_name=_('Alternative title (dublin core)'))

    abstract      = IndexedMultiLangField(DC.abstract, required=True,
                                          verbose_name=_('Abstract (dublin core)'),
                                          attrs={'presentation': 'textarea'})

    creator       = IndexedTextField(DC.creator, required=True,
                                     verbose_name=_('Creator (dublin core)'))

    contributor   = IndexedTextField(DC.contributor, required=True,
                                     verbose_name=_('Contributor (dublin core)'))

    dateSubmitted = IndexedDateField(DC.dateSubmitted, required=True,
                                     verbose_name=_('Date submitted (dublin core)'))

    dateAvailable = IndexedDateField(DC.dateAvailable, required=True,
                                     verbose_name=_('Date available (dublin core)'))

#
# register it so that FedoraObject.objects.get(...) knows which class to instantiate
#
FedoraTypeManager.register_model(DCObject, on_has_predicate=[DC.title])
