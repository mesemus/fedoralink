# -*- coding: utf-8 -*-
import bleach
from django import template
from django.utils.safestring import mark_safe
import django.utils.translation
from dateutil import parser as dateparser
import logging
from fedoralink.auth import AuthManager

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