import re
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def avatar_upload_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1]
    return f'avatars/{instance.user.id}/{instance.user.id}.{ext}'


def paginate_queryset(queryset, page, per_page=20):
    paginator = Paginator(queryset, per_page)
    try:
        return paginator.page(page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


MANA_SYMBOL_RE = re.compile(r'\{([^}]+)\}')

def format_mana_cost(mana_string):
    if not mana_string:
        return ''
    def replace(match):
        symbol = match.group(1).lower().replace('/', '')
        return f'<span class="ms ms-{symbol} ms-cost"></span>'
    return MANA_SYMBOL_RE.sub(replace, mana_string)
