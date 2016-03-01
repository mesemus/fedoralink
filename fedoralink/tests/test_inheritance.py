import django
from rdflib.namespace import DC

from unittest import TestCase

from fedoralink.common_namespaces.dc import DCObject
from fedoralink.indexer.fields import IndexedTextField

django.setup()


class BlahObject(DCObject):
    blah = IndexedTextField(DC.blah)


class DCObjectTestCase(TestCase):
    def setUp(self):
        pass

    def test_inheritance(self):
        blah = BlahObject()
        self.assertEquals(len(blah._meta.fields), 8)
