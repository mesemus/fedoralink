import django.db.models

from fedoralink.forms import LangFormTextField, LangFormTextAreaField, RepositoryFormMultipleFileField


class IndexedField:
    def __init__(self, rdf_name, required=False, verbose_name=None, attrs=None):
        self.rdf_name     = rdf_name
        self.required     = required
        self.verbose_name = verbose_name
        self.attrs        = attrs if attrs else {}


class IndexedLanguageField(IndexedField, django.db.models.Field):

    def formfield(self, **kwargs):
        if 'textarea' in self.attrs.get('presentation', ''):
            defaults = {'form_class': LangFormTextAreaField}
        else:
            defaults = {'form_class': LangFormTextField}

        defaults.update(kwargs)
        return super().formfield(**defaults)

    def get_internal_type(self):
        return 'TextField'


class IndexedTextField(IndexedField, django.db.models.Field):

    def get_internal_type(self):
        return 'TextField'


class IndexedDateField(IndexedField, django.db.models.DateTimeField):
    pass