import datetime
import traceback

import django.db.models
import django.forms
from dateutil import parser
from django.apps import apps
from django.db.models.signals import class_prepared
from rdflib import Literal, XSD, URIRef

from fedoralink.forms import LangFormTextField, LangFormTextAreaField, MultiValuedFedoraField, GPSField, \
    FedoraChoiceField
from fedoralink.models import FedoraObject
from fedoralink.utils import StringLikeList


class IndexedField:
    __global_order = 0

    MANDATORY   = 'mandatory'
    RECOMMENDED = 'recommended'
    OPTIONAL    = "optional"

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False, attrs=None, level=None):
        self.rdf_name     = rdf_name
        self.required     = required
        self.verbose_name = verbose_name
        self.attrs        = attrs if attrs else {}
        self.multi_valued = multi_valued
        self.order = IndexedField.__global_order
        if level is None:
            if required:
                level = IndexedField.MANDATORY
            else:
                level = IndexedField.OPTIONAL
        self.level = level
        IndexedField.__global_order += 1

    def convert_to_rdf(self, value):
        raise Exception("Conversion to RDF on %s not supported yet" % type(self))

    def convert_from_rdf(self, value):
        raise Exception("Conversion from RDF on %s not supported yet" % type(self))


class IndexedLanguageField(IndexedField, django.db.models.Field):

    def __init__(self, rdf_name, required=False, verbose_name=None,
                 multi_valued=False, attrs=None, help_text=None, level=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs, level=level)
        # WHY is Field's constructor not called without this?
        # noinspection PyCallByClass,PyTypeChecker
        django.db.models.Field.__init__(self, verbose_name=verbose_name, help_text=help_text)

    def formfield(self, **kwargs):
        if 'textarea' in self.attrs.get('presentation', ''):
            defaults = {'form_class': LangFormTextAreaField}
        else:
            defaults = {'form_class': LangFormTextField}

        defaults.update(kwargs)
        return super().formfield(**defaults)

    @staticmethod
    def _convert_val_to_rdf(x):
        if isinstance(x, Literal):
            if x.datatype:
                return x
            if x.language:
                return Literal(x.value, lang=x.language)
            return Literal(x.value, datatype=XSD.string)
        return Literal(x if isinstance(x, str) else str(x), datatype=XSD.string)

    def convert_to_rdf(self, value):
        print("converting to rdf", value)
        return IndexedLanguageField._convert_val_to_rdf(value)

    def convert_from_rdf(self, value):
        return StringLikeList(value)


class IndexedTextField(IndexedField, django.db.models.Field):

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False,
                 attrs=None, help_text=None, level=None, choices=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs, level=level)
        # WHY is Field's constructor not called without this?
        # noinspection PyCallByClass,PyTypeChecker
        django.db.models.Field.__init__(self, verbose_name=verbose_name, help_text=help_text, choices=choices)

    def formfield(self, **kwargs):
        if self.multi_valued:
            defaults = {'form_class': MultiValuedFedoraField}
        elif self.choices:
            defaults = {'choices_form_class': FedoraChoiceField}
        else:
            defaults = {'form_class': django.forms.CharField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def get_internal_type(self):
        return None

    def convert_to_rdf(self, value):
        if value is None or not value.strip():
            return []
        return Literal(value, datatype=XSD.string)

    def convert_from_rdf(self, value):
        return str(value)


class IndexedIntegerField(IndexedField, django.db.models.IntegerField):

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False,
                 attrs=None, help_text=None, level=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs, level=level)
        # WHY is Field's constructor not called without this?
        # noinspection PyCallByClass,PyTypeChecker
        django.db.models.IntegerField.__init__(self, verbose_name=verbose_name, help_text=help_text)

    def convert_to_rdf(self, value):
        if value is None:
            return []
        return Literal(value, datatype=XSD.integer)

    def convert_from_rdf(self, value):
        return value.value


class IndexedDateTimeField(IndexedField, django.db.models.DateTimeField):

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False,
                 attrs=None, help_text=None, level=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs, level=level)
        # WHY is Field's constructor not called without this?
        # noinspection PyCallByClass,PyTypeChecker
        django.db.models.DateTimeField.__init__(self, verbose_name=verbose_name, help_text=help_text)

    def convert_to_rdf(self, value):
        print("Converting to rdf", value)
        if value is None:
            return []
        if isinstance(value, datetime.datetime):
            return Literal(value, datatype=XSD.datetime)
        else:
            raise AttributeError("Conversion of %s to datetime is not supported in "
                                 "fedoralink/indexer/fields.py" % type(value))

    def convert_from_rdf(self, data):
        value = data.toPython()
        print("Converting from RDF", value)
        if value:
            if isinstance(value, datetime.datetime):
                return value
            if value is "None":         # TODO:  neskor odstranit
                return None
            val = value
            # noinspection PyBroadException
            try:
                # handle 2005-06-08 00:00:00+00:00
                if val[-3] == ':':
                    val = val[:-3] + val[-2:]
                val = datetime.datetime.strptime(val, '%Y-%m-%d %H:%M:%S%z')
                return val
            except:
                # noinspection PyBroadException
                try:
                    if val[-3] == ':':
                        val = val[:-3] + val[-2:]
                    return parser.parse(val)
                except:
                    traceback.print_exc()
                    pass

            raise AttributeError("Conversion of %s [%s] to datetime is not supported in "
                                 "fedoralink/indexer/models.py" % (type(value), value))


class IndexedDateField(IndexedField, django.db.models.DateField):

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False,
                 attrs=None, help_text=None, level=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs, level=level)
        # WHY is Field's constructor not called without this?
        # noinspection PyCallByClass,PyTypeChecker
        django.db.models.DateField.__init__(self, verbose_name=verbose_name, help_text=help_text)

    def convert_to_rdf(self, value):
        if value is None:
            return []
        if isinstance(value, datetime.datetime):
            return Literal(value.date(), datatype=XSD.date)
        elif isinstance(value, datetime.date):
            return Literal(value, datatype=XSD.date)
        else:
            raise AttributeError("Conversion of %s to date is not supported in "
                                 "fedoralink/indexer/fields.py" % type(value))

    def convert_from_rdf(self, data):
        if data.value:
            if isinstance(data.value, datetime.datetime):
                return data.value.date()
            if isinstance(data.value, datetime.date):
                return data.value
            if data.value is "None":      # TODO:  neskor odstranit
                return None
            # noinspection PyBroadException
            try:
                # handle 2005-06-08
                val = data.value
                val = datetime.datetime.strptime(val, '%Y-%m-%d').date()
                return val
            except:
                traceback.print_exc()
                pass

            raise AttributeError("Conversion of %s [%s] to date is not supported in "
                                 "fedoralink/indexer/models.py" % (type(data.value), data.value))


def register_model_lookup(field, related_model):
    if isinstance(related_model, str):
        app_label, model_name = related_model.split('.')
        try:
            field.related_model = apps.get_registered_model(app_label, model_name)
        except LookupError:
            def resolve(**kwargs):
                clz = kwargs['sender']
                # noinspection PyProtectedMember
                if clz._meta.app_label == app_label and clz._meta.object_name == model_name:
                    field.related_model = clz
                    class_prepared.disconnect(resolve, weak=False)

            class_prepared.connect(resolve, weak=False)
    else:
        field.related_model = related_model


class IndexedLinkedField(IndexedField, django.db.models.Field):

    def __init__(self, rdf_name, related_model, required=False, verbose_name=None, multi_valued=False,
                 attrs=None, help_text=None, level=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs, level=level)
        # WHY is Field's constructor not called without this?
        # noinspection PyCallByClass,PyTypeChecker
        django.db.models.Field.__init__(self, verbose_name=verbose_name, help_text=help_text)

        register_model_lookup(self, related_model)

    def get_internal_type(self):
        return 'TextField'

    def convert_to_rdf(self, value):
        if value is None:
            return []
        return URIRef(value.id)

    def convert_from_rdf(self, value):
        if not value:
            return None
        return self.related_model.objects.get(pk=value)


class IndexedBinaryField(IndexedField, django.db.models.Field):

    def __init__(self, rdf_name, related_model, required=False, verbose_name=None, multi_valued=False, attrs=None,
                 help_text=None, level=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs, level=level)
        # WHY is Field's constructor not called without this?
        # noinspection PyCallByClass,PyTypeChecker
        django.db.models.Field.__init__(self, verbose_name=verbose_name, help_text=help_text)

        register_model_lookup(self, related_model)

    def formfield(self, **kwargs):
        # This is a fairly standard way to set up some defaults
        # while letting the caller override them.
        defaults = {'form_class': django.forms.FileField}
        defaults.update(kwargs)
        return super(IndexedBinaryField, self).formfield(**defaults)

    def convert_to_rdf(self, value):
        if value is None:
            return []
        return URIRef(value.id)

    def convert_from_rdf(self, value):
        if not value:
            return None
        return self.related_model.objects.get(pk=value)


class IndexedGPSField(IndexedField, django.db.models.Field):

    def __init__(self, rdf_name, required=False, verbose_name=None, attrs=None, help_text=None, level=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=False, attrs=attrs, level=level)
        # WHY is Field's constructor not called without this?
        # noinspection PyCallByClass,PyTypeChecker
        django.db.models.Field.__init__(self, verbose_name=verbose_name, help_text=help_text)

    def formfield(self, **kwargs):
        defaults = {'form_class': GPSField}

        defaults.update(kwargs)
        return super().formfield(**defaults)

    def get_internal_type(self):
        return 'TextField'

    def convert_to_rdf(self, value):
        if value is None or not value.strip():
            return []
        return Literal(value, datatype=XSD.string)

    def convert_from_rdf(self, value):
        return value
