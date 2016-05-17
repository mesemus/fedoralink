import copy
from django import forms
from django.conf import settings
from django.forms.utils import flatatt
from django.template import Context
from django.template.loader import render_to_string
from django.utils.html import escape
from django.utils.safestring import mark_safe
from rdflib import Literal
from rdflib.namespace import DC

from fedoralink.models import FedoraObject
from fedoralink.utils import StringLikeList

__author__ = 'simeki'


class LangWidget(forms.MultiWidget):
    def decompress(self, value):
        ret = []
        for lang in settings.LANGUAGES:
            lcode = lang[0]
            found = None
            if value:
                for v in value:
                    if v.language == lcode:
                        found = str(v)
            ret.append(found)
        return ret

    def render(self, name, value, attrs=None):
        if self.is_localized:
            for widget in self.widgets:
                widget.is_localized = self.is_localized
        # value is a list of values, each corresponding to a widget
        # in self.widgets.
        if not isinstance(value, list) or isinstance(value, StringLikeList):
            value = self.decompress(value)
        output = []
        final_attrs = self.build_attrs(attrs)
        id_ = final_attrs.get('id', None)
        output.append('<div class="multilang-field-group">')
        for i, widget in enumerate(self.widgets):
            try:
                widget_value = value[i]
            except IndexError:
                widget_value = None
            if id_:
                final_attrs = dict(final_attrs, id='%s_%s' % (id_, i))
            output.append('<label class="multilang-child-field">')
            output.append('<span>%s</span>' % str(escape(widget.attrs['title'])))
            output.append(widget.render(name + '_%s' % i, widget_value, final_attrs))
            output.append('</label>')
        output.append('</div>')
        return mark_safe(self.format_output(output))


class LangFormField(forms.MultiValueField):

    def __init__(self, *args, **kwargs):
        self._field_widget = kwargs.pop('field_widget', forms.Textarea)
        fields = [
            forms.CharField() for lang in settings.LANGUAGES
        ]
        self.languages = settings.LANGUAGES
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        ret = []
        for d, lang in zip(data_list, settings.LANGUAGES):
            if d and d.strip():
                ret.append(Literal(d, lang=lang[0]))
        return ret


class LangFormTextField(LangFormField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.widget = LangWidget(
                                widgets= [
                                        forms.TextInput({'title' : lang[1], 'class': 'lang-input form-control'})
                                            for lang in settings.LANGUAGES
                                ])


class LangFormTextAreaField(LangFormField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.widget = LangWidget(
                                widgets= [
                                        forms.Textarea({'title' : lang[1], 'class': 'lang-input form-control'})
                                            for lang in settings.LANGUAGES
                                ])


class FedoraChoiceField(forms.TypedChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs.update({'widget': ChoiceWidget})
        super().__init__(*args, **kwargs)


class ChoiceWidget(forms.Select):
    def render_options(self, choices, selected_choices):
        return super().render_options(choices, [str(x) for x in selected_choices])


def get_preferred_presentation(fedora_field):
    from fedoralink.indexer.fields import IndexedIntegerField, IndexedDateTimeField
    choices=getattr(fedora_field, 'choices')

    if isinstance(fedora_field, IndexedIntegerField):
        return forms.IntegerField(), forms.NumberInput()
    if isinstance(fedora_field, IndexedDateTimeField):
        return forms.DateTimeField(), forms.DateTimeInput()
    if fedora_field.attrs.get('presentation', '') == 'textarea':
        return forms.CharField(), forms.Textarea()
    if choices:
        return forms.ChoiceField(choices=choices), ChoiceWidget(choices=choices)
    return forms.CharField(), forms.TextInput()


class DynamicMultiValueWidget(forms.MultiWidget):
    def decompress(self, value):
        return value

    def render(self, name, value, attrs=None):
        if self.is_localized:
            for widget in self.widgets:
                widget.is_localized = self.is_localized
        output = []
        final_attrs = self.build_attrs(attrs)
        id_ = final_attrs.get('id', None)
        html_widgets = []
        for i, widget in enumerate(self.widgets):
            try:
                widget_value = value[i]
            except IndexError:
                widget_value = None
            if id_:
                final_attrs = dict(final_attrs, id='%s_%s' % (id_, i))
            html_widgets.append((str(widget.attrs['title']),
                                 widget.render(name + '_%s' % i, widget_value, final_attrs)))

        output.append(render_to_string('fedoralink_ui/edit_field_dynamic.html', context=Context({
            'widgets': html_widgets
        })))

        return mark_safe(self.format_output(output))


class MultiValuedFedoraField(forms.MultiValueField):

    def __init__(self, *args, **kwargs):

        self.child_field = kwargs.pop('child_field')

        fields = [
            self.child_field
        ]

        self.widget = DynamicMultiValueWidget(widgets=[self.child_field.widget])

        super().__init__(fields, *args, **kwargs)

    def setup_fields(self, count):
        widgets = []
        fields = []
        for i in range(max(1, count)):
            fld = copy.copy(self.child_field)
            if self.required:
                fld.required = self.required
            fields.append(fld)
            widgets.append(fld.widget)
        self.fields = tuple(fields)
        self.widget.widgets = tuple(widgets)

    def compress(self, data_list):
        print("data list", data_list, self.fields)
        return data_list


class RepositoryFormMultipleFileField(forms.MultiValueField):

    def __init__(self, *args, **kwargs):
        fields = [
            forms.FileField(widget=forms.FileInput())
        ]
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        # return array of streams
        return data_list


class GPSWidget(forms.TextInput):
    def render(self, name, value, attrs=None):
        return render_to_string('fedoralink/partials/google_map_input_field.html', context=Context({
            'widget': super().render(name, value, attrs)
        }))


class GPSField(forms.CharField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget = GPSWidget()


class FedoraForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        inst = kwargs.get('instance', None)
        post = kwargs.get('data', None)
        super().__init__(*args, **kwargs)
        print("Fedora form", inst, post)
        for fldname, fld in self.fields.items():
            if isinstance(fld, MultiValuedFedoraField):
                if post:
                    count = 1
                    while True:
                        if "%s_%s" % (fldname, count) not in post:
                            break
                        count += 1
                elif inst:
                    count = len(getattr(inst, fldname))
                else:
                    raise Exception("Need to pass either instance or POST parameters")

                fld.setup_fields(count)

    class Media:
        js = ('fedoralink_ui/dynamic_multi_value.js', )


class LinkedWidget(forms.TextInput):
    def _format_value(self, value):
        from fedoralink_ui.templatetags.fedoralink_tags import rdf2lang

        if isinstance(value, StringLikeList):
            # TODO: implement correctly multi-valued fields !!!
            print("Bad implementation - implement correctly multi-valued fields!")
            if len(value)>0:
                value = value[0]
            else:
                value = None

        if isinstance(value, FedoraObject):
            if DC.title in value.metadata:
                value = (rdf2lang(value.metadata[DC.title]), str(value.id))
            else:
                value = (str(value.id), str(value.id))

        return value

    def render(self, name, value, attrs=None):
        if value is None:
            value = ''
        final_attrs = self.build_attrs(attrs, type=self.input_type, name=name)

        if value != '':
            value = self._format_value(value)

        print(type(self.model_field))

        return render_to_string('fedoralink_ui/edit_field_linked.html', Context({
            'value' : value,
            'flatatt' : flatatt(final_attrs),
            'attrs': final_attrs,
            'model_field': self.model_field,
            'field': self.field
        }))


class LinkedField(forms.CharField):
    def __init__(self, *args, **kwargs):
        self.model_field = kwargs.pop('model_field', None)
        if 'widget' not in kwargs:
            kwargs['widget'] = LinkedWidget
        super().__init__(*args, **kwargs)
        self.widget.model_field = self.model_field
        self.widget.field = self

    def to_python(self, value):
        value = super().to_python(value)
        return FedoraObject.objects.get(pk=value)

