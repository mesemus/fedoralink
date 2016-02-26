import json
import logging

from django.conf import settings
from django.core.management import BaseCommand
from django.db import connections

from fedoralink.indexer import FEDORA_ID_FIELD, FEDORA_PARENT_FIELD, FEDORA_TYPE_FIELD
from fedoralink.type_manager import FedoraTypeManager

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('config_repository_index')

import importlib

def class_for_name(module_name, class_name):

    # load the module, will raise ImportError if module cannot be loaded
    m = importlib.import_module(module_name)
    # get the class, will raise AttributeError if class cannot be found
    c = getattr(m, class_name)
    return c

class Command(BaseCommand):
    args = '<model name>*'
    help = """

        Configures elasticsearch index

        Arguments for this command is a list of classes. All the classes are read, their
        'indexed_fields' are inspected and an index is created for each of the classes.

    """
    can_import_settings = True

    def handle(self, *args, **options):

        FedoraTypeManager.populate()

        models = list(args)

        for model_name in models:
            fields = {}

            split_model_name  = model_name.split('.')
            indexer_model_name = '_'.join(split_model_name)
            module_name = '.'.join(split_model_name[:-1])
            split_model_name  = split_model_name[-1]
            class_for_name(module_name, split_model_name)
            modelclz = FedoraTypeManager.get_model_class(split_model_name)

            for field in modelclz.indexed_fields:
                if field.name not in fields:
                    fields[field.name] = field

            indexer = connections['repository'].indexer

            existing_mapping = indexer.get_mapping(indexer_model_name)
            existing_properties = existing_mapping.get('properties', {})

            new_mapping = {
            }

            new_properties = {
            }

            fields['_fedora_id']      = FEDORA_ID_FIELD
            fields['_fedora_parent']  = FEDORA_PARENT_FIELD
            fields['_fedora_type']    = FEDORA_TYPE_FIELD

            for fldname, field in fields.items():
                if fldname in existing_properties:
                    continue

                if 'binary' in field.field_type:
                    continue

                props = {}
                new_properties[fldname] = props

                if 'lang' in field.field_type:
                    props['type'] = 'nested'
                    props['properties'] = self.gen_languages_mapping()
                elif 'text' in field.field_type or 'string' in field.field_type:
                    props['type'] = 'string'
                    props['copy_to'] = fldname + "__exact"
                    new_properties[fldname + "__exact"] = {
                        'type': 'string',
                        'index': 'not_analyzed'
                    }
                elif 'date' in field.field_type:
                    props['type'] = 'date'
                    props['index'] = 'not_analyzed'
                elif 'int' in field.field_type:
                    props['type'] = 'long'
                    props['index'] = 'not_analyzed'
                else:
                    raise Exception("Mapping type %s not handled yet" % field.field_type)


            new_mapping['properties'] = new_properties
            print(json.dumps(new_mapping, indent=4))

            indexer.save_mapping(indexer_model_name, new_mapping)


    @staticmethod
    def gen_languages_mapping():
        ret = {
            lang[0] : { 'type': 'string', 'copy_to': 'all' } for lang in settings.LANGUAGES
        }
        if 'en' in ret:
            ret['en']['analyzer'] = 'english'
        if 'cs' in ret:
            ret['cs']['analyzer'] = 'czech'

        ret['null'] = { 'type' : 'string', 'copy_to': 'all' }
        ret['all']  = { 'type' : 'string' }

        return ret
