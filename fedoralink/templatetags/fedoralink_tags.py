# -*- coding: utf-8 -*-
import base64
import inspect
import json
import logging
from urllib.parse import quote

import django.utils.translation
import zlib
from django import template
from django.conf import settings
from django.core.signing import TimestampSigner
from django.core.urlresolvers import reverse
from django.template import Context
from django.template.loader import select_template
from rdflib import Literal

from fedoralink.indexer.fields import IndexedLinkedField, IndexedBinaryField
from fedoralink.models import FedoraObject
from fedoralink.utils import fullname

register = template.Library()
log = logging.getLogger('fedoralink.tags')

@register.inclusion_tag('fedoralink/facet.html', takes_context=True)
def render_facet_box(context, facet, id_to_name_mapping):

    # print("id to name", id_to_name_mapping, facet)

    facet_id = facet[0]
    facet_values = facet[1]
    facet_name = id_to_name_mapping[facet_id]

    return {
        'id'     : facet_id,
        'esc_id' : facet_id.replace('@', '__'),
        'name'   : facet_name,
        'values' : facet_values[:10],
        'all_values'   : facet_values,
        'selected_values' : context.request.GET.getlist('facet__' + facet_id)
    }


@register.tag
def ifinfacets(parser, token):
    nodelist = parser.parse(('endifinfacets',))
    parser.delete_first_token()
    try:
        tagname, facet_id, facet_value = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            "%r tag requires exactly two arguments" % token.contents.split()[0]
        )
    return FacetContainmentNode(nodelist, facet_id, facet_value)


class FacetContainmentNode(template.Node):
    def __init__(self, nodelist, facet_id, facet_value):
        self.nodelist = nodelist
        self.facet_id = template.Variable(facet_id)
        self.facet_value = template.Variable(facet_value)

    def render(self, context):
        facet_id = self.facet_id.resolve(context)
        facet_value = self.facet_value.resolve(context)

        facet_id = 'facet__' + facet_id
        if facet_id not in context.request.GET:
            return ''

        lst = context.request.GET.getlist(facet_id)
        if facet_value not in lst:
            return ''

        return self.nodelist.render(context)


@register.filter
def rdf2lang(rdfliteral, lang=None):
    if not isinstance(rdfliteral, Literal) and not isinstance(rdfliteral, list) and not isinstance(rdfliteral, tuple):
        return rdfliteral

    default_value = ''
    try:
        if lang is None:
            lang = django.utils.translation.get_language()
        if lang:
            lang = lang.split("-")[0]
        if isinstance(rdfliteral, Literal):
            rdfliteral = [rdfliteral]

        if len(rdfliteral):
            for l in rdfliteral:
                if not isinstance(l, Literal):
                    return l                        # fallback for multi non-literals

                if lang and l.language == lang or (not lang and (l.language is None or l.language == '')):
                    return l.value
                elif not l.language:
                    default_value = l.value

            if default_value is None:
                for l in rdfliteral:
                    if l.value:
                        return l.value
    except:
        pass

    return default_value

@register.filter
def id_from_path(idval):
    idval = str(idval)
    repository_url = settings.DATABASES['repository']['REPO_URL']

    # won't be the case in production, but in development django treats these two interchangeably
    idval = idval.replace('127.0.0.1', 'localhost')
    repository_url = repository_url.replace('127.0.0.1', 'localhost')

    if idval.startswith(repository_url): #TODO: edit to use more repositories
        if repository_url.endswith("/"):
            return quote(idval[len(repository_url):]).replace('/', '_')
        else:
            return quote(idval[len(repository_url) + 1:]).replace('/', '_')
    else:
        raise AttributeError('%s is not from repository %s' %(idval, repository_url) )


@register.filter
def download_object_from_fedora(pk):
    try:
        return FedoraObject.objects.get(pk=str(pk))
    except:
        return None

@register.filter
def split_to_array(val, separator=','):
    return val.split(separator)

@register.filter
def get_fields(object, level=None):
    meta_fields = object._meta.fields
    fields = ()
    for meta in meta_fields:
        if level is not None and meta.level != level:
            continue
        meta_name = getattr(meta, "name")
        name = getattr(meta, "verbose_name")
        if name is None:
            name = meta_name

        val = getattr(object, meta_name)

        if not val:
            val = None
        elif isinstance(val, list):
            for x in val:
                print("val",  x.value)
                if str(x):
                    break
            else:
                val = None
        else:
            print(val, type(val))
        fields += ((name, val, meta_name),)

    return fields


@register.simple_tag(takes_context=True)
def render_links(context, object, link_name):
    templates = [fullname(x).replace('.', '/') + '/' + link_name + '_link.html' for x in inspect.getmro(type(object))]
    templates.append('fedoralink/partials/link.html')
    context = Context(context)
    context['links'] = getattr(object, link_name)
    chosen_template = select_template(templates)
    return chosen_template.template.render(context)


@register.filter
def get_form_fields(form, level=None):
    object = form.instance
    meta_fields = object._meta.fields
    fields = ()
    for meta in meta_fields:
        if level is not None and meta.level != level:
            continue
        meta_name = getattr(meta, "name")
        name = getattr(meta, "verbose_name")
        if name is None:
            name = meta_name
        fields += ((name, form[meta_name], meta_name),)

    return fields


def model_name(model):
    return model._meta.app_label + "/" + model._meta.object_name


def fedora_user_classes(inst):
    for x in inspect.getmro(type(inst)):
         if 'bound' not in x.__name__ and x.__name__ not in ('object', 'FedoraObject', 'IndexableFedoraObject'):
             yield x


@register.simple_tag(takes_context=True)
def render_field_view(context, containing_object, meta_name, name, value):
    if value is None or containing_object is None:
        return ''
    templates = [model_name(x) + '/' + meta_name + '_view.html' for x in fedora_user_classes(containing_object)]

    fieldtype = containing_object._meta.fields_by_name[meta_name]

    if isinstance(fieldtype, IndexedLinkedField) or isinstance(fieldtype, IndexedBinaryField):
        templates += [model_name(x) + '/' + fieldtype.__class__.__name__ + '/' +
                      model_name(fieldtype.related_model) + '_view.html' for x in fedora_user_classes(containing_object)]

    templates += [model_name(x) + '/' + fieldtype.__class__.__name__ + '_view.html' for x in fedora_user_classes(containing_object)]

    if isinstance(fieldtype, IndexedLinkedField) or isinstance(fieldtype, IndexedBinaryField):
        templates.append('{0}/{1}_view.html'.format(fullname(fieldtype.__class__).replace('.', '/'), model_name(fieldtype.related_model)))
    templates.append('{0}_view.html'.format(fullname(fieldtype.__class__).replace('.', '/')))

    templates.append('fedoralink/partials/view.html')
    print(templates)

    context = Context(context)
    context['field'] = containing_object._meta.fields_by_name[meta_name]

    chosen_template = select_template(templates)

    return chosen_template.template.render(context)


@register.simple_tag(takes_context=True)
def render_field_edit(context, form, meta_name, name, field):
    templates = [fullname(x).replace('.', '/') + '/' + meta_name + '_edit.html' for x in
                 fedora_user_classes(form.instance)]

    fieldtype = form.instance._meta.fields_by_name[meta_name]

    templates += [fullname(x).replace('.', '/') + '/' + fullname(fieldtype.__class__).replace('.', '_') + '_edit.html'
                    for x in fedora_user_classes(object)]

    templates.append('{0}_edit.html'.format(fullname(fieldtype.__class__).replace('.', '/')))

    templates.append('fedoralink/partials/edit.html')
    print(templates)
    context = Context(context)
    context['field'] = field
    chosen_template = select_template(templates)
    return chosen_template.template.render(context)


@register.simple_tag(takes_context=True)
def render_linked_field(context, linked_object, field_name, containing_object):

    if linked_object is None:
        return "Unable to get linked object from %s" % getattr(containing_object, field_name)

    templates = [model_name(x) + '/' + field_name + '_linked_view.html' for x in fedora_user_classes(containing_object)]

    fieldtype = containing_object._meta.fields_by_name[field_name]

    for y in fedora_user_classes(containing_object):
        templates.extend([
            '{0}/{1}_linked_view.html'.format(model_name(y),
                                              model_name(x)) for x in fedora_user_classes(linked_object)
        ])

    templates.extend([
        '{0}/{1}_linked_view.html'.format(fullname(fieldtype.__class__).replace('.', '/'),
                                          model_name(x)) for x in fedora_user_classes(linked_object)
    ])
    templates.append('{0}_linked_view.html'.format(fullname(fieldtype.__class__).replace('.', '/')))

    templates.append('fedoralink/partials/linked_view.html')
    print(templates)

    context = Context(context)
    context['field'] = containing_object._meta.fields_by_name[field_name]
    context['value'] = linked_object
    context['containing_object'] = containing_object

    chosen_template = select_template(templates)

    return chosen_template.template.render(context)


@register.simple_tag(takes_context=True)
def render_linked_standalone_field(context, linked_object):

    templates = []

    for y in fedora_user_classes(linked_object):
        templates.append('fedoralink/indexer/fields/IndexedLinkedField/{0}_linked_view.html'.format(model_name(y).replace('.', '/')))
    templates.append('fedoralink/partials/linked_view.html')

    print(templates)

    context = Context(context)
    context['value'] = linked_object

    chosen_template = select_template(templates)

    return chosen_template.template.render(context)


@register.filter
def get_fedora_object_page_link(linked_object, view_type):
    from fedoralink.views import ModelViewRegistry
    return reverse(ModelViewRegistry.get_view(type(linked_object), view_type), kwargs={'pk': id_from_path(linked_object.pk)})


@register.filter
def get_dir_obj(object):
    print(dir(object))
    print('Typ:', type(object))
    return ''


@register.filter
def get_languages_data(bound_field):
    return zip (range(len(bound_field.data)),bound_field.data, bound_field.field.languages)

@register.simple_tag
def linked_form_field_model(model_form, field):
    model_class = model_form._meta.model
    model_field = model_class._meta.fields_by_name[field.name]
    related_model = model_field.related_model

    # 'related_app'          : related_model._meta.app_label,
    # 'related_class'        : related_model._meta.object_name,

    data_url = [{
        'referencing_app'      : model_class._meta.app_label,
        'referencing_class'    : model_class._meta.object_name,
        'referencing_field'    : field.name,
        'referencing_instance' : model_form.instance.pk,
        'current_value'        : field.value()
    }]

    from fedoralink.views import ModelViewRegistry
    link_view = ModelViewRegistry.get_view(related_model, 'link')

    data_url = base64.b64encode(zlib.compress(json.dumps(data_url).encode('utf-8')))
    signer = TimestampSigner(salt='linked_form_field_model')
    data_url = signer.sign(data_url)

    return reverse(link_view, kwargs={'parametry': ''}) + '?linking=' + data_url

@register.simple_tag
def linked_form_field_label_url(model_form, field):
    model_class = model_form._meta.model
    model_field = model_class._meta.fields_by_name[field.name]
    related_model = model_field.related_model

    from fedoralink.views import ModelViewRegistry
    title_view = ModelViewRegistry.get_view(related_model, 'link_title')


    if field.value():
        try:
            return reverse(title_view, kwargs={'pk': id_from_path(field.value())})
        except AttributeError:
            # url not in repository, use default value
            pass

    return reverse(title_view, kwargs={'pk': '0'})[:-1]



@register.simple_tag
def detail_view_url(obj):
    from fedoralink.views import ModelViewRegistry

    return reverse(ModelViewRegistry.get_view(type(obj), 'detail'), kwargs={'pk': id_from_path(obj.pk)})