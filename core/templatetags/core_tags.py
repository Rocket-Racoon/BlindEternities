import re
from django import template
from django.utils.safestring import mark_safe
from core.utils import format_mana_cost
from core.symbolmap import ManaSymbol

register = template.Library()

SYMBOL_RE = re.compile(r"\{([^}]+)\}")


def _symbol_to_html(symbol):
    css_class = ManaSymbol.to_css(symbol)
    return f'<abbr class="{css_class}" title="{{{symbol}}}"></abbr>'


@register.filter
def mana_cost(value):
    return mark_safe(format_mana_cost(value))


@register.filter
def dfc_mana_cost(card):
    """
    Render mana cost for a card, showing both faces for DFCs separated by //.
    Usage: {{ entry.card|dfc_mana_cost }}
    """
    faces = list(card.faces.all())  # uses prefetch if available
    if len(faces) >= 2:
        parts = []
        for face in sorted(faces, key=lambda f: f.face_index):
            parts.append(format_mana_cost(face.mana_cost) if face.mana_cost else "")
        # Only show separator if at least one face has a cost
        if any(parts):
            separator = ' <span class="text-gray-400 dark:text-gray-600 mx-0.5">//</span> '
            return mark_safe(separator.join(parts))
        return ""
    # Single-face: use the card-level mana cost
    return mark_safe(format_mana_cost(card.mana_cost))


@register.filter
def oracle_symbols(value):
    """
    Convierte los símbolos {X} en el texto oracle a spans de mana-font.
    Preserva saltos de línea como <br>.
    """
    if not value:
        return value

    def replace(match):
        return _symbol_to_html(match.group(1))

    result = SYMBOL_RE.sub(replace, value)
    result = result.replace("\n", "<br>")
    return mark_safe(result)


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
def replace(value, args):
    """Replace characters in a string. Usage: {{ value|replace:"_: " }}"""
    old, new = args.split(":", 1)
    return value.replace(old, new)


@register.filter
def get_item(dictionary, key):
    """Permite acceder a un dict por key variable en templates."""
    if isinstance(dictionary, dict):
        return dictionary.get(key, "")
    return ""