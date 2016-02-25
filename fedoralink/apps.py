# -*- coding: utf-8 -*-
from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


def do_index(sender, **kwargs):

    from fedoralink.models import IndexableFedoraObject
    from django.db import connections
    from django.conf import settings

    instance = kwargs['instance']
    db = kwargs['using']

    print("do_index called", db, instance, settings.DATABASES[db].get('USE_INTERNAL_INDEXER', False))

    if settings.DATABASES[db].get('USE_INTERNAL_INDEXER', False) and isinstance(instance, IndexableFedoraObject):
        print("Running indexer")
        indexer = connections[db].indexer
        indexer.reindex(instance)


class ApplicationConfig(AppConfig):
    name = 'fedoralink'
    verbose_name = _("fedoralink")

    def ready(self):
        super().ready()

        from django.db.models.signals import post_save

        post_save.connect(do_index, dispatch_uid='indexer', weak=False)