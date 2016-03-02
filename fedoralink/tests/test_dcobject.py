import django
import random
from rdflib.namespace import DC

django.setup()

import logging
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(level=logging.INFO)

from unittest import TestCase

from rdflib import Literal

from fedoralink.common_namespaces.dc import DCObject
from fedoralink.indexer.fields import IndexedLanguageField
from fedoralink.models import FedoraObject
from fedoralink.utils import StringLikeList


class DCObjectTestCase(TestCase):
    def setUp(self):
        root = FedoraObject.objects.get(pk='')
        dco = root.create_child('hello%s' % random.randint(0, 100000), flavour=DCObject)
        dco.save()

    def test_dcobject_creation(self):
        dco = DCObject()
        self.assertIsNotNone(dco._meta)
        self.assertIsNotNone(dco._meta.fields)
        self.assertNotEqual(len(dco._meta.fields), 0, "Expecting fields in _meta, got %s" % dco._meta.fields)

        for fld in dco._meta.fields:
            if isinstance(fld, IndexedLanguageField):
                self.assertEquals(getattr(dco, fld.name), [])
            else:
                self.assertEquals(getattr(dco, fld.name), None)

        dco.creator = 'Annie'
        self.assertIsInstance(dco.creator, Literal)
        self.assertEquals(str(dco.creator), 'Annie')

        dco.title = [
            Literal('title', lang='en'),
            Literal('název', lang='cs'),
            Literal('orig')
        ]
        self.assertIsInstance(dco.title, StringLikeList)

    def test_dcobject_upload(self):
        root = FedoraObject.objects.get(pk='')
        dco = root.create_child('hello%s' % random.randint(0, 100000), flavour=DCObject)
        dco.save()

        dcb = DCObject.objects.get(pk=dco.pk)
        self.assertEquals(dcb.title, dco.title)

        dcc = FedoraObject.objects.get(pk=dco.pk)
        self.assertEquals(dcc.title, dco.title)

    def test_dcobject_update(self):
        root = FedoraObject.objects.get(pk='')
        dco = root.create_child('hello%s' % random.randint(0, 100000), flavour=DCObject)
        dco.save()

        dco.title = 'Hello world'
        dco.save()

        dcb = DCObject.objects.get(pk=dco.pk)
        self.assertEquals(len(dcb[DC.title]), 1)
        self.assertEquals(dcb.title, dco.title)

        dco.title = 'Blah'
        dco.save()

        dcb = DCObject.objects.get(pk=dco.pk)
        self.assertEquals(len(dcb[DC.title]), 1)
        self.assertEquals(dcb.title, dco.title)

    def test_meta(self):

        root = FedoraObject.objects.get(pk='')
        dco = root.create_child('hello%s' % random.randint(0, 100000), flavour=DCObject)
        dco.save()

        dco.title = 'Hello world'
        dco.save()

        dcb = DCObject.objects.get(pk=dco.pk)
        self.assertIsNotNone(dcb._meta)

    def test_meta_search(self):
        dco = list(DCObject.objects.all())[0]
        self.assertIsNotNone(dco._meta)
