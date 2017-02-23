from django import template

register = template.Library()

# added previous context ...
@register.inclusion_tag('autobreadcrumbs_tag.html', takes_context=True)
def autobreadcrumbs_tag_context(context):
    """
    Template tag to output HTML for full breadcrumbs using template
    ``autobreadcrumbs_tag.html``.

    Example:
        ::

            {% load autobreadcrumb %}
            {% autobreadcrumbs_tag %}
    """
    if 'autobreadcrumbs_elements' in context:
        elements = []
        for item in context['autobreadcrumbs_elements']:
            tpl = template.Template(item.title)
            title = tpl.render(template.Context(context))

            elements.append(dict(zip(
                (
                    'url', 'title', 'name',
                    'view_args', 'view_kwargs'
                ),
                (
                    item.path, title, item.name,
                    item.view_args, item.view_kwargs
                )
            )))
        ret = {
            k:v for k,v in context.flatten().items()
        }
        ret['elements'] = elements

        return ret

    return {}