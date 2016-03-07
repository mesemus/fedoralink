from django import forms
from django.template import Context
from django.template.loader import render_to_string
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.conf import settings
from rdflib import Literal


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
        if not isinstance(value, list):
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


def get_preferred_presentation(fedora_field):
    from fedoralink.indexer.fields import IndexedIntegerField, IndexedDateTimeField

    if isinstance(fedora_field, IndexedIntegerField):
        return forms.IntegerField(), forms.NumberInput()
    if isinstance(fedora_field, IndexedDateTimeField):
        return forms.DateTimeField(), forms.DateTimeInput()
    if fedora_field.attrs.get('presentation', '') == 'textarea':
        return forms.CharField(), forms.Textarea()
    return forms.CharField(), forms.TextInput()


class DynamicMultiValueWidget(forms.MultiWidget):
    def decompress(self, value):
        return value

    def render(self, name, value, attrs=None):
        if self.is_localized:
            for widget in self.widgets:
                widget.is_localized = self.is_localized
        # value is a list of values, each corresponding to a widget
        # in self.widgets.
        if not isinstance(value, list):
            value = self.decompress(value)
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

        output.append(render_to_string('fedoralink/partials/dynamic_multi_value.html', context=Context({
            'widgets': html_widgets
        })))

        return mark_safe(self.format_output(output))


class MultiValuedFedoraField(forms.MultiValueField):

    def __init__(self, *args, **kwargs):

        fields = [
        ]

        self.widget = DynamicMultiValueWidget(widgets=[])

        super().__init__(fields, *args, **kwargs)

    def setup_fields(self, fedora_field, count):
        widgets = []
        fields = []
        for i in range(max(1, count)):
            fld, widget = get_preferred_presentation(fedora_field)
            if self.required:
                fld.required = self.required
            fields.append(fld)
            widgets.append(widget)
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

                fld.setup_fields(inst._meta.fields_by_name[fldname], count)
