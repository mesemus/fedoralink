# encoding: utf-8

from __future__ import unicode_literals
from django.core.management import call_command

from django.core.management.base import BaseCommand
from django.db import connections

from fedoralink.authentication.Credentials import Credentials
from fedoralink.authentication.as_user import as_user
from fedoralink.models import FedoraObject


class Command(BaseCommand):
    args = ''
    help = 'Reindexuje cely obsah repozitare'

    def handle(self, *args, **options):
        obj = FedoraObject.objects.get(pk='')
        indexer = connections['repository'].indexer
        self.reindex(indexer, obj)

    def reindex(self, indexer, obj, level=0):

        if 'fedora:' in obj.id:
            return

        print(obj.id)
        obj.update()

        indexer.reindex(obj)

        print("   " * level, obj.id, type(obj))

        for c in obj.children:
            self.reindex(indexer, c, level+1)