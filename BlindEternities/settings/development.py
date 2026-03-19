"""
BlindEternities — Local Development Settings
"""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']


# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ──────────────────────────────────────────────
# EMAIL Backend
# ──────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# ──────────────────────────────────────────────
# CORS — allow all origins in dev
# ──────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True


# ──────────────────────────────────────────────
# DEBUG TOOLBAR
# ──────────────────────────────────────────────
INSTALLED_APPS += ['debug_toolbar', 'django_extensions']
MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
INTERNAL_IPS = ['127.0.0.1']
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
}


# ──────────────────────────────────────────────
# LOGGING — verbose in dev
# ──────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',  
            'propagate': False,
        },
    },
}