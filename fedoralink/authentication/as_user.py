import threading

from fedoralink.authentication.Credentials import Credentials
from fedoralink.middleware import FedoraUserDelegationMiddleware

fedora_auth_local = threading.local()

class as_user:
    def __init__(self, credentials):
        self.credentials = credentials
        self.original_credentials = None

    def __enter__(self):
        if(hasattr(fedora_auth_local,'Credentials')):
            self.original_credentials = getattr(fedora_auth_local, 'Credentials')
        setattr(fedora_auth_local, 'Credentials', self.credentials)
        return fedora_auth_local

    def __exit__(self, exc_type, exc_val, exc_tb):
        setattr(fedora_auth_local, 'Credentials', self.original_credentials)


class as_delegated_user:
    def __init__(self, username, groups):
        self.username = username
        self.groups   = groups

    def __enter__(self):
        if hasattr(FedoraUserDelegationMiddleware.thread_local_storage, 'fedora_on_behalf_of'):
            self.original_username = FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of
            self.original_groups   = FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of_groups
        else:
            self.original_groups = self.original_username = None

        FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of = self.username
        FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of_groups = self.groups

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.original_username:
            FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of = self.original_username
            FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of_groups = self.original_groups
        else:
            delattr(FedoraUserDelegationMiddleware.thread_local_storage, 'fedora_on_behalf_of')
            delattr(FedoraUserDelegationMiddleware.thread_local_storage, 'fedora_on_behalf_of_groups')


class as_admin:
    def __init__(self):
        pass

    def __enter__(self):
        if hasattr(FedoraUserDelegationMiddleware.thread_local_storage, 'fedora_on_behalf_of'):
            self.original_username = FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of
            self.original_groups   = FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of_groups
            delattr(FedoraUserDelegationMiddleware.thread_local_storage, 'fedora_on_behalf_of')
            delattr(FedoraUserDelegationMiddleware.thread_local_storage, 'fedora_on_behalf_of_groups')
        else:
            self.original_groups = self.original_username = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.original_username:
            FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of = self.original_username
            FedoraUserDelegationMiddleware.thread_local_storage.fedora_on_behalf_of_groups = self.original_groups
