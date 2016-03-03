import inspect

from fedoralink.forms import LangFormTextField, LangFormTextAreaField, RepositoryFormMultipleFileField
import django.db.models


class RepositoryMultipleFileField(django.db.models.Field):

    def formfield(self, **kwargs):
        defaults = {'form_class': RepositoryFormMultipleFileField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    def get_internal_type(self):
        return 'TextField'


class DjangoMetadataBridge:
    """
    A _meta implementation for IndexableFedoraObject
    """
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
            fld.null = not fld.required
            fld.blank = not fld.required
            fld.attname = fld.name
            fld.model = model_class
            self.concrete_fields.append(fld)

        self.fields = self.concrete_fields
        self.app_label = model_class.__module__
        self.object_name = model_class.__name__

