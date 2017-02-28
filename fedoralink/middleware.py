import threading
from urllib.parse import quote_plus


class FedoraUserDelegationMiddleware:

    thread_local_storage = threading.local()

    def process_request(self, request):
        fedora_on_behalf_of_groups = []
        if request.user.is_anonymous():
            fedora_on_behalf_of = ['urn:fedora:anonymous']
        else:
            fedora_on_behalf_of = [ FedoraUserDelegationMiddleware.email_to_urn(request.user.username) ]
            fedora_on_behalf_of_groups.append(FedoraUserDelegationMiddleware.group_to_urn('authenticated'))
            for grp in request.user.groups.all():
                fedora_on_behalf_of_groups.append(FedoraUserDelegationMiddleware.group_to_urn(grp.name))

        FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of = fedora_on_behalf_of
        FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of_groups = fedora_on_behalf_of_groups

    @staticmethod
    def email_to_urn(name):
        return FedoraUserDelegationMiddleware.get_escaped_id('urn:', name)

    @staticmethod
    def get_escaped_id(prefix, name):
        name = name.replace(',', '__comma__')
        print("name", type(name), name)
        if '@' not in name:
            return prefix + quote_plus(name)
        name = name.split('@')
        return prefix + quote_plus(name[1]) + '/' + quote_plus(name[0])

    @staticmethod
    def group_to_urn(name):
        return FedoraUserDelegationMiddleware.get_escaped_id('urn:django:', name)

    @staticmethod
    def get_on_behalf_of():
        return getattr(FedoraUserDelegationMiddleware.thread_local_storage, 'fedora_on_behalf_of')

    @staticmethod
    def get_on_behalf_of_groups():
        return getattr(FedoraUserDelegationMiddleware.thread_local_storage, 'fedora_on_behalf_of_groups')

    @staticmethod
    def is_enabled():
        return hasattr(FedoraUserDelegationMiddleware.thread_local_storage, 'fedora_on_behalf_of')
