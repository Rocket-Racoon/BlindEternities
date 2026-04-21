"""
Blind Eternities — Base Settings
Shared across all environments. Never used directly.
"""
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ""),
)
environ.Env.read_env(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')


# SECURITY WARNING: don't run with debug turned on in production!
ALLOWED_HOSTS = []

# ──────────────────────────────────────────────
# Apps
# ──────────────────────────────────────────────
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
    'crispy_forms',
    'crispy_bootstrap5',
    # 'rest_framework',
    # 'rest_framework_simplejwt',
    # 'rest_framework_simplejwt.token_blacklist',
    # 'django_filters',
    # 'drf_spectacular',
    # 'corsheaders',
    # 'django_celery_beat',
    # 'django_celery_results',
]

LOCAL_APPS = [
    'core',         # Utilities, base models, mixins
    'nexus',        # Users & Profiles
    'multiverse',   # Cards catalog (Scryfall sync)
    'tolarian',     # Collections & Decks
    'phyrexian',    # Game statistics
    'omenpath',     # Market & trading activity
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ──────────────────────────────────────────────
# Middleware
# ──────────────────────────────────────────────
MIDDLEWARE = [
    'core.middleware.DatabaseLockedMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'BlindEternities.urls'
WSGI_APPLICATION = 'BlindEternities.wsgi.application'


# ──────────────────────────────────────────────
# Templates
# ──────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Core context processors
                "core.context_processors.user_profile",
                "core.context_processors.magic_formats",
                "core.context_processors.site_settings",
                # Omenpath context processors
                "omenpath.context_processors.pending_trades",
            ],
        },
    },
]


# ──────────────────────────────────────────────
# Auth - Password validation
# ──────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1

# -- ALL AUTH --
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
SOCIALACCOUNT_ADAPTER = "nexus.adapters.NexusSocialAccountAdapter"
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
    "github": {
        "SCOPE": ["user:email"],
    },
}


# ──────────────────────────────────────────────
# Internationalization
# ──────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Monterrey'
USE_I18N = True
USE_TZ = True


# ──────────────────────────────────────────────
# Static files (CSS, JavaScript, Images)
# ──────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ──────────────────────────────────────────────
# Crispy Forms
# ──────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

 
# ──────────────────────────────────────────────
# SCRYFALL
# ──────────────────────────────────────────────
SCRYFALL_API_BASE = 'https://api.scryfall.com'
SCRYFALL_BULK_DATA_URL = 'https://api.scryfall.com/bulk-data'
SCRYFALL_HEADERS = {
    "User-Agent": "BlindEternities/1.0",
    "Accept": "application/json",
}
SCRYFALL_REQUEST_DELAY = 0.1    # 100ms between requests (rate limit)
SCRYFALL_TIMEOUT_SHORT  = 15    # para endpoints simples
SCRYFALL_TIMEOUT_LONG   = 300   # para bulk data
SCRYFALL_BATCH_SIZE     = 500   # registros por batch en sync


# ──────────────────────────────────────────────
# Market pricing (omenpath) — credentials optional; adapters disable when empty
# ──────────────────────────────────────────────
TCGPLAYER_PUBLIC_KEY  = env("TCGPLAYER_PUBLIC_KEY",  default="")
TCGPLAYER_PRIVATE_KEY = env("TCGPLAYER_PRIVATE_KEY", default="")
CARDMARKET_APP_TOKEN            = env("CARDMARKET_APP_TOKEN",            default="")
CARDMARKET_APP_SECRET           = env("CARDMARKET_APP_SECRET",           default="")
CARDMARKET_ACCESS_TOKEN         = env("CARDMARKET_ACCESS_TOKEN",         default="")
CARDMARKET_ACCESS_TOKEN_SECRET  = env("CARDMARKET_ACCESS_TOKEN_SECRET",  default="")
