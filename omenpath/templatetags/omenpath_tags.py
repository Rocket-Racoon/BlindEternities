from django import template

from omenpath.stats import trade_stats_for

register = template.Library()


@register.simple_tag
def trade_stats(user):
    """
    Return {'count': int, 'last_at': datetime|None} for a user.
    Usage:
      {% load omenpath_tags %}
      {% trade_stats user as stats %}
      {% include "omenpath/partials/trade_badge.html" with stats=stats %}
    """
    return trade_stats_for(user)
