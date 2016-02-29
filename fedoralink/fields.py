import inspect

from fedoralink.forms import LangFormTextField, LangFormTextAreaField, RepositoryFormMultipleFileField
import django.db.models


class LangTextField(django.db.models.Field):

    def formfield(self, **kwargs):
        defaults = {'form_class': LangFormTextField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def get_internal_type(self):
        return 'TextField'


class LangTextAreaField(django.db.models.Field):

    def formfield(self, **kwargs):
        defaults = {'form_class': LangFormTextAreaField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def get_internal_type(self):
        return 'TextField'


class RepositoryMultipleFileField(django.db.models.Field):

    def formfield(self, **kwargs):
        defaults = {'form_class': RepositoryFormMultipleFileField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def get_internal_type(self):
        return 'TextField'


class DjangoMetadataBridge:
    def __init__(self, model_class, fields):
        self._fields = fields
        self.virtual_fields  = []
        self.concrete_fields = []
        self.many_to_many    = []
        self.verbose_name = getattr(model_class, "verbose_name", model_class.__name__)
        self.model_class = model_class

        process_fields=set()
        for fld in fields:
            if fld.name in process_fields:
                continue
            process_fields.add(fld.name)
            if 'lang' in fld.field_type:
                if 'string' in fld.field_type:
                    afld = LangTextField()
                else:
                    afld = LangTextAreaField()
                afld.label = fld.verbose_name
            else:
                afld = self.get_django_model_field(fld)(verbose_name=fld.verbose_name)

            afld.null = not fld.required
            afld.blank = not fld.required
            afld.name = fld.name
            afld.attname = fld.name
            afld.model = model_class
            afld.fedora_field = fld
            self.concrete_fields.append(afld)

        self.fields = self.concrete_fields
        self.app_label = model_class.__module__
        self.object_name = model_class.__name__

    @staticmethod
    def get_django_model_field(fld):
        if 'date' in fld.field_type:
            return django.db.models.DateTimeField
        if 'binary' in fld.field_type:
            if 'multi' in fld.field_type:
                return RepositoryMultipleFileField
            return django.db.models.FileField
        if 'string' in fld.field_type:
            return django.db.models.CharField
        else:
            return django.db.models.TextField
