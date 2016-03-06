# -*- coding: utf-8 -*-
import inspect

import bleach
from django import template
from django.conf import settings
from django.utils.safestring import mark_safe
import django.utils.translation
from dateutil import parser as dateparser
import logging

from rdflib import Literal

from fedoralink.auth import AuthManager
from urllib.parse import quote
from django.template import Context
from django.template.loader import select_template

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
    repository_url = settings.DATABASES['repository']['REPO_URL']
    if idval.startswith(repository_url): #TODO: edit to use more repositories
        if repository_url.endswith("/"):
            return quote(idval[len(repository_url):]).replace('/', '_')
        else:
            return quote(idval[len(repository_url) + 1:]).replace('/', '_')
    else:
        raise AttributeError('%s is not from repository %s' %(idval, repository_url) )


@register.filter
def download_object_from_fedora(pk):
    return FedoraObject.objects.get(pk=str(pk))

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
        fields += ((name, getattr(object, meta_name), meta_name),)

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


@register.filter
def get_dir_obj(object):
    print(dir(object))
    print('Typ:', type(object))
    return ''


@register.filter
def get_languages_data(bound_field):
    return zip (range(len(bound_field.data)),bound_field.data, bound_field.field.languages)