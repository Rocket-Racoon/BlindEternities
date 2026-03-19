"""
WSGI config for Blind Eternities project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE', 
    'BlindEternities.settings.development'
)

application = get_wsgi_application()
