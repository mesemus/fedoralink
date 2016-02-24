import inspect
from django.core.management import BaseCommand
import inflection as inflection
from fedoralink.indexer import MULTI_LANG
from fedoralink.manager import FedoraManager
from fedoralink.models import FedoraObject
from fedoralink.type_manager import FedoraTypeManager
import logging

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('config_repository_index')

import importlib


def class_for_name(module_name, class_name):

    # load the module, will raise ImportError if module cannot be loaded
    m = importlib.import_module(module_name)
    # get the class, will raise AttributeError if class cannot be found
    c = getattr(m, class_name)
    return c


def indexer_name(indexed_field):
    postfix = '_'

    if 'text' in indexed_field.field_type:
        postfix += 't'              # in default solr schema _t is always stored

    elif indexed_field.stored:
        postfix += 's'

    return indexed_field.prefix + indexed_field.name + postfix


class Command(BaseCommand):
    args = '<model name>*'
    help = """

        Configures repository index and creates LDPath scripts inside
        fcrepo/rest/fedora:system/fedora:transform/fedora:ldpath/

        Arguments for this command is a list of classes. All the classes are read, their
        'indexed_fields' are inspected and a single LDPath file is generated (to cover
        the case of multiple inheritance, where item has more types).

        The name of the uploaded file is the name of the models in alphabetical order,
        converted from CamelCase to underlined words, with '__' as a separator between
        models.

        For example, for the following args:

            QualificationWork DataRichObject

        the created resource will have name

            data_rich_object__qualification_work

    """
    can_import_settings = True

    def handle(self, *args, **options):

        FedoraTypeManager.populate()

        models = list(args)
        models.sort()

        fields = {}

        model_classes = set()

        for model_name in models:
            model_name  = model_name.split('.')
            module_name = '.'.join(model_name[:-1])
            model_name  = model_name[-1]
            class_for_name(module_name, model_name)
            modelclz = FedoraTypeManager.get_model_class(model_name)

            for clz in inspect.getmro(modelclz):
                if clz == FedoraObject or issubclass(clz, FedoraObject):
                    model_classes.add(clz.__name__)

            for field in modelclz.indexed_fields:
                if field.name not in fields:
                    fields[field.name] = field
                else:
                    fields[field.name] = field.combine(fields[field.name])
                print(field)
            print()

        ldpath = [
            'id      = . :: xsd:string ;'
        ]
        all_fields = []
        for field in fields.values():
            field_indexer_name = indexer_name(field)
            field_rdf_name = field.rdf_name

            if field_indexer_name.endswith('_t'):
                if MULTI_LANG.issubset(field.field_type):
                    from django.conf import settings
                    langstrings = []
                    for langi, lang in enumerate(settings.LANGUAGES):
                        if langi:
                            langstrings.append(', " ", ')
                        langstrings.append('<{0}>[@{1}]'.format(field_rdf_name, lang[0]))
                        all_fields.append('<{0}>[@{1}]'.format(field_rdf_name, lang[0]))
                        all_fields.append('" "')

                    ldpath.append(
                        """
                        {0} = fn:concat({1}) :: {2};
                        """.format(field_indexer_name, ''.join(langstrings), field.xml_schema_type).strip()
                    )
                else:
                    ldpath.append(
                        """
                        {0} = <{1}> :: {2};
                        """.format(field_indexer_name, field_rdf_name, field.xml_schema_type).strip()
                    )
                    all_fields.append('<%s>' % field_rdf_name)

                    all_fields.append('" "')

                if MULTI_LANG.issubset(field.field_type):
                    # multi lang field, generate all languages from settings.py
                    from django.conf import settings
                    for lang in settings.LANGUAGES:
                        ldpath.append(
                           """
                                {3}__{0} = <{1}>[@{3}] :: {2};
                            """.format(field_indexer_name, field_rdf_name, field.xml_schema_type, lang[0]).strip()
                        )
                        ldpath.append(
                           """
                                sort__{3}__{0}_s = <{1}>[@{3}] :: {2};
                            """.format(field_indexer_name[:-3], field_rdf_name, field.xml_schema_type, lang[0]).strip()
                        )
                else:
                    ldpath.append(
                        """
                        sort__{0}_s = <{1}> :: {2};
                        """.format(field_indexer_name[:-3], field_rdf_name, field.xml_schema_type).strip()
                    )
            else:
                if MULTI_LANG.issubset(field.field_type):
                    from django.conf import settings
                    langstrings = []
                    for langi, lang in enumerate(settings.LANGUAGES):
                        if langi:
                            langstrings.append(', " ", ')
                        langstrings.append('<{0}>[@{1}]'.format(field_rdf_name, lang[0]))
                        all_fields.append('<{0}>[@{1}]'.format(field_rdf_name, lang[0]))
                        all_fields.append('" "')

                    ldpath.append(
                        """
                        {0} = fn:concat({1}) :: {2};
                        """.format(field_indexer_name, ''.join(langstrings), field.xml_schema_type).strip()
                    )
                else:
                    ldpath.append(
                        """
                        {0} = <{1}> :: {2};
                        """.format(field_indexer_name, field_rdf_name, field.xml_schema_type).strip()
                    )

                if MULTI_LANG.issubset(field.field_type):
                    # multi lang field, generate all languages from settings.py
                    from django.conf import settings
                    for lang in settings.LANGUAGES:
                        ldpath.append(
                           """
                                {3}__{0} = <{1}>[@{3}] :: {2};
                            """.format(field_indexer_name, field_rdf_name, field.xml_schema_type, lang[0]).strip()
                        )

        ldpath.append('fedora_parent_id_t = <http://fedora.info/definitions/v4/repository#hasParent> :: xsd:string;')

        ldpath.append('fedora_mixin_types_t = "%s" :: xsd:string;' % ' '.join(model_classes))

        if all_fields:
            ldpath.append('solr_all_fields_t  = fn:concat(%s) :: xsd:string;' % ', '.join(all_fields))

        ldpath = '\n'.join(ldpath)

        print(ldpath)

        name = '__'.join([inflection.underscore(x.split('.')[-1]) for x in models])

        mgr = FedoraManager.get_manager()
        mgr.connection.direct_put('fedora:system/fedora:transform/fedora:ldpath/' + name + "/fedora:Container",
                                  data=ldpath,
                                  content_type='application/rdf+ldpath')

        # prepare schema inside solr - not needed, using wildcards
        # solr = FedoraManager.get_indexer()

        # for field in fields.values():
        #    solr.install_indexed_field(field)

        log.info("Transformation created with name `%s'", name)
