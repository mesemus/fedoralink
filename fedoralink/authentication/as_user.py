import threading

from fedoralink.authentication.Credentials import Credentials

fedora_auth_local = threading.local()

class as_user:
    def __init__(self, credentials):
        self.credentials = credentials

    def __enter__(self):
        setattr(fedora_auth_local, 'Credentials', self.credentials)
        return fedora_auth_local

    def __exit__(self, exc_type, exc_val, exc_tb):
        setattr(fedora_auth_local, 'Credentials', None)
