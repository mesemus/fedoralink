import django.db.models

from fedoralink.forms import RepositoryFormMultipleFileField


class RepositoryMultipleFileField(django.db.models.Field):

    def formfield(self, **kwargs):
        defaults = {'form_class': RepositoryFormMultipleFileField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def get_internal_type(self):
        return 'TextField'


