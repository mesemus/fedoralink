from django.forms import TextInput
from django.forms import CharField as FormsCharField, FileField as FormsFileField
from django.forms import MultiWidget, MultiValueField, Textarea, FileInput
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.conf import settings
from rdflib import Literal

__author__ = 'simeki'


class LangWidget(MultiWidget):
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


class LangFormField(MultiValueField):

    def __init__(self, *args, **kwargs):
        self._field_widget = kwargs.pop('field_widget', Textarea)
        fields = [
            FormsCharField() for lang in settings.LANGUAGES
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
                                        TextInput({'title' : lang[1], 'class': 'lang-input form-control'})
                                            for lang in settings.LANGUAGES
                                ])


class LangFormTextAreaField(LangFormField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.widget = LangWidget(
                                widgets= [
                                        Textarea({'title' : lang[1], 'class': 'lang-input form-control'})
                                            for lang in settings.LANGUAGES
                                ])


class RepositoryFormMultipleFileField(MultiValueField):

    def __init__(self, *args, **kwargs):
        fields = [
            FormsFileField(widget=FileInput())
        ]
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        # return array of streams
        return data_list
