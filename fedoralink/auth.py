import functools
from .utils import get_class


class AuthHandler:

    # noinspection PyMethodMayBeStatic
    def has_rights(self, inst, user, right_string):
        raise Exception("Implement this method")


class AuthManager:

    @classmethod
    @functools.lru_cache(maxsize=128)
    def get_handler(cls, clazz):
        from django.conf import settings
        auth_plugins = settings.REPOSITORY_PLUGINS['auth']
        for modelclz, auth_plugin_clz in auth_plugins.items():
            modelclz = get_class(modelclz)
            if issubclass(clazz, modelclz):
                return get_class(auth_plugin_clz)()
        raise Exception("""Authentication handler for class %s is not defined in settings.py. Add
REPOSITORY_PLUGINS = {
    'auth': {
        'full.path.to.model.class' : 'full.path.to.auth.handler.class (subclass of fedoralink.auth.AuthHandler)'
    }
}""")
