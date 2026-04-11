from django.db.utils import OperationalError
from django.http import HttpResponse
from django.template.loader import render_to_string


class DatabaseLockedMiddleware:
    """Return a 503 page instead of crashing when SQLite is locked."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except OperationalError as exc:
            if "database is locked" in str(exc):
                html = render_to_string("503.html", request=request)
                return HttpResponse(html, status=503, headers={
                    "Retry-After": "10",
                })
            raise
