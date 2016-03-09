from django.utils.translation import ugettext_lazy as _

from fedoralink.common_namespaces.dc import DCObject
from fedoralink.fedorans import ACL
from fedoralink.indexer.fields import IndexedTextField


class AclCollection(DCObject):

    class Meta:
        rdf_types = (ACL.AclCollection, )


class Authorization(DCObject):

    agent        = IndexedTextField(ACL.agent, verbose_name=_('People allowed to access a resource'),
                                    multi_valued=True)

    agent_class  = IndexedTextField(ACL.agentClass, verbose_name=_('Groups of people allowed to access a resource'),
                                    multi_valued=True)

    mode         = IndexedTextField(ACL.mode, verbose_name=_('Resource access mode, either acl:Read or acl:Write'),
                                    multi_valued=True)

    access_to   = IndexedTextField(ACL.accessTo, verbose_name=_('Resource to which this object applies'),
                                    multi_valued=True)

    access_to_class = IndexedTextField(ACL.accessToClass, verbose_name=_('RDF class of resources to which this authorization applies'),
                                    multi_valued=True)

    class Meta:
        rdf_types = (ACL.Authorization, )
