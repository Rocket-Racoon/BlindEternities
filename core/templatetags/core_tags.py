from django import template
from django.utils.safestring import mark_safe
from core.utils import format_mana_cost

register = template.Library()


@register.filter
def mana_cost(value):
    return mark_safe(format_mana_cost(value))


@register.simple_tag(takes_context=True)
def is_owner(context, obj):
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False
    return getattr(obj, 'user', None) == request.user


@register.simple_tag(takes_context=True)
def active_url(context, url_name):
    request = context.get('request')
    if request and request.resolver_match.url_name == url_name:
        return 'active'
    return ''


@register.inclusion_tag("core/partials/paginator.html", takes_context=True)
def paginator(context, page_obj):
    return {
        "page_obj": page_obj,
        "request": context["request"],
    }
    

@register.filter
def get_item(dictionary, key):
    """Permite acceder a un dict por key variable en templates."""
    if isinstance(dictionary, dict):
        return dictionary.get(key, "")
    return ""