import threading
from threading import current_thread


class FedoraUserDelegationMiddleware:

    thread_local_storage = threading.local()

    def process_request(self, request):
        if request.user.is_anonymous():
            fedora_on_behalf_of = ['urn:fedora:anonymous']
        else:
            fedora_on_behalf_of = [ FedoraUserDelegationMiddleware.email_to_urn(request.user.username) ]
            for grp in request.user.groups.all():
                fedora_on_behalf_of.append( FedoraUserDelegationMiddleware.email_to_urn(grp.name) )

        FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of = fedora_on_behalf_of

    @staticmethod
    def email_to_urn(name):
        if '@' not in name:
            return 'urn:' + name
        name = name.split('@')
        return 'urn:' + name[1] + '/' + name[0]

    @staticmethod
    def get_on_behalf_of():
        return getattr(FedoraUserDelegationMiddleware.thread_local_storage, 'fedora_on_behalf_of')

    @staticmethod
    def is_enabled():
        return hasattr(FedoraUserDelegationMiddleware.thread_local_storage, 'fedora_on_behalf_of')