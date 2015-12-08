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
    def __init__(self, fields):
        self._fields = fields
        self.virtual_fields  = []
        self.concrete_fields = []
        self.many_to_many    = []

        for fld in fields:
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
            self.concrete_fields.append(afld)

        self.fields = self.concrete_fields

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
