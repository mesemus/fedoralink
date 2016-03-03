import django.db.models
import django.forms

from fedoralink.forms import LangFormTextField, LangFormTextAreaField, RepositoryFormMultipleFileField


class IndexedField:
    __global_order = 0

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False, attrs=None):
        self.rdf_name     = rdf_name
        self.required     = required
        self.verbose_name = verbose_name
        self.attrs        = attrs if attrs else {}
        self.multi_valued = multi_valued
        self.order = IndexedField.__global_order
        IndexedField.__global_order += 1


class IndexedLanguageField(IndexedField, django.db.models.Field):

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False, attrs=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs)
        # WHY is Field's constructor not called without this?
        django.db.models.Field.__init__(self, verbose_name=verbose_name)


    def formfield(self, **kwargs):
        if 'textarea' in self.attrs.get('presentation', ''):
            defaults = {'form_class': LangFormTextAreaField}
        else:
            defaults = {'form_class': LangFormTextField}

        defaults.update(kwargs)
        return super().formfield(**defaults)
    #
    # for debugging
    #
    # def __getattribute__(self,name):
    #     attr = object.__getattribute__(self, name)
    #     if hasattr(attr, '__call__') and name not in ('__class__', ):
    #         def newfunc(*args, **kwargs):
    #             print('before calling %s' %attr.__name__)
    #             result = attr(*args, **kwargs)
    #             print('done calling %s: %s' %(attr.__name__, result))
    #             try:
    #                 if len(result) == 2:
    #                     print("in")
    #             except:
    #                 pass
    #             return result
    #         return newfunc
    #     else:
    #         return attr


class IndexedTextField(IndexedField, django.db.models.Field):

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False, attrs=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs)
        # WHY is Field's constructor not called without this?
        django.db.models.Field.__init__(self, verbose_name=verbose_name)

    def get_internal_type(self):
        return 'TextField'


class IndexedIntegerField(IndexedField, django.db.models.IntegerField):

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False, attrs=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs)
        # WHY is Field's constructor not called without this?
        django.db.models.IntegerField.__init__(self, verbose_name=verbose_name)


class IndexedDateField(IndexedField, django.db.models.DateTimeField):

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False, attrs=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs)
        # WHY is Field's constructor not called without this?
        django.db.models.DateTimeField.__init__(self, verbose_name=verbose_name)


class IndexedLinkedField(IndexedField, django.db.models.Field):

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False, attrs=None, model=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs)
        # WHY is Field's constructor not called without this?
        django.db.models.Field.__init__(self, verbose_name=verbose_name)

        self.model = model

    def get_internal_type(self):
        return 'TextField'


class IndexedBinaryField(IndexedField, django.db.models.Field):

    def __init__(self, rdf_name, required=False, verbose_name=None, multi_valued=False, attrs=None, model=None):
        super().__init__(rdf_name, required=required,
                         verbose_name=verbose_name, multi_valued=multi_valued, attrs=attrs)
        # WHY is Field's constructor not called without this?
        django.db.models.Field.__init__(self, verbose_name=verbose_name)

        self.model = model

    def formfield(self, **kwargs):
        # This is a fairly standard way to set up some defaults
        # while letting the caller override them.
        defaults = {'form_class': django.forms.FileField}
        defaults.update(kwargs)
        return super(IndexedBinaryField, self).formfield(**defaults)

    def get_internal_type(self):
        return 'FileField'