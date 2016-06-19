from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.base.features import BaseDatabaseFeatures
from ..connection import FedoraConnection

__author__ = 'simeki'


class DatabaseFeatures(BaseDatabaseFeatures):
    pass


class DatabaseOps:

    def max_name_length(self):
        return 100000


class FakeValidation:
    def check_field(self, something, **kwargs):
        print("FakeValidation: check_field", type(something), something, kwargs)
        return []


class DatabaseWrapper(BaseDatabaseWrapper):

    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper, self).__init__(*args, **kwargs)
        self.features = DatabaseFeatures(self)
        self._commit_on_exit = False
        self.ops = DatabaseOps()

    def get_connection_params(self):
        pass

    def get_new_connection(self, conn_params):
        return FedoraConnection(self.settings_dict['REPO_URL'],
                                self.settings_dict.get('USERNAME', None),
                                self.settings_dict.get('PASSWORD', None))

    def _set_autocommit(self, autocommit):
        pass

    def init_connection_state(self):
        pass

    def _commit(self):
        self.connection.commit()

    def _rollback(self):
        self.connection.rollback()

    def _close(self):
        pass # does nothing

    @property
    def commit_on_exit(self):
        return self._commit_on_exit

    @commit_on_exit.setter
    def commit_on_exit(self, val):
        self._commit_on_exit = val
        if self.connection:
            if self._commit_on_exit:
                self.connection.begin_transaction()
            else:
                self.connection.commit()

    @property
    def indexer(self):
        return import_class(self.settings_dict['SEARCH_ENGINE'])(self.settings_dict)

    @property
    def validation(self):
        return FakeValidation()


def import_class( kls ):
    parts = kls.split('.')
    module = ".".join(parts[:-1])
    m = __import__( module )
    for comp in parts[1:]:
        m = getattr(m, comp)
    return m