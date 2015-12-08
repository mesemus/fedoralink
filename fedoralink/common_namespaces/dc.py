from rdflib.namespace import DC
from django.utils.translation import ugettext_lazy as _

from fedoralink.models import IndexableFedoraObject
from fedoralink.type_manager import FedoraTypeManager


#
# DCObject is indexable and provides .title and .creator property, that get mapped to
# DC.* predicates in RDF by simple_namespace_mapper
#
from fedoralink.indexer import IndexedField, DATE, MULTI_LANG, TEXT, STRING


class DCObject(IndexableFedoraObject):

    indexed_fields = [
        IndexedField('title', DC.title, stored=True, indexed=True, type=MULTI_LANG | TEXT, prefix='dc_',
                     required=True, verbose_name=_('Název (dublin core)')),
        IndexedField('alternative', DC.alternative, stored=True, indexed=True, type=TEXT, prefix='dc_',
                     verbose_name=_('Alternativní název (dublin core)')),
        IndexedField('abstract', DC.abstract, stored=True, indexed=True, type=MULTI_LANG | TEXT, prefix='dc_',
                     verbose_name=_('Abstrakt (dublin core)')),
        IndexedField('creator', DC.creator, stored=True, indexed=True, type=STRING, prefix='dc_',
                     verbose_name=_('Autor (dublin core)')),
        IndexedField('contributor', DC.contributor, stored=True, indexed=True, type=STRING, prefix='dc_',
                     verbose_name=_('Přispěvovatel (dublin core)')),
        IndexedField('dateSubmitted', DC.dateSubmitted, stored=True, indexed=True, type=DATE, prefix='dc_',
                     verbose_name=_('Datum uložení (dublin core)')),
        IndexedField('dateAvailable', DC.dateAvailable, stored=True, indexed=True, type=DATE, prefix='dc_',
                     verbose_name=_('Datum zpřístupnění (dublin core)')),
    ]

#
# register it so that FedoraObject.objects.get(...) knows which class to instantiate
#
FedoraTypeManager.register_model(DCObject, on_has_predicate=[DC.title])
