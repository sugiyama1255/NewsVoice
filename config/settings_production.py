"""Production settings for NewsVoice.

Use this module with:
DJANGO_SETTINGS_MODULE=config.settings_production
"""

import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .settings import *


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")

DEBUG = False

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", True)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", GEMINI_MODEL)

NEWSVOICE_SIMPLE_TTS_ENABLED = env_bool(
    "NEWSVOICE_SIMPLE_TTS_ENABLED",
    NEWSVOICE_SIMPLE_TTS_ENABLED,
)
NEWSVOICE_HIGH_QUALITY_TTS_ENABLED = env_bool(
    "NEWSVOICE_HIGH_QUALITY_TTS_ENABLED",
    NEWSVOICE_HIGH_QUALITY_TTS_ENABLED,
)
NEWSVOICE_DEFAULT_TTS_PROVIDER = os.environ.get(
    "NEWSVOICE_DEFAULT_TTS_PROVIDER",
    NEWSVOICE_DEFAULT_TTS_PROVIDER,
)
NEWSVOICE_DEFAULT_VOICE_NAME = os.environ.get(
    "NEWSVOICE_DEFAULT_VOICE_NAME",
    NEWSVOICE_DEFAULT_VOICE_NAME,
)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_DEFAULT_MODEL_ID = os.environ.get("ELEVENLABS_DEFAULT_MODEL_ID", ELEVENLABS_DEFAULT_MODEL_ID)
ELEVENLABS_DEFAULT_OUTPUT_FORMAT = os.environ.get(
    "ELEVENLABS_DEFAULT_OUTPUT_FORMAT",
    ELEVENLABS_DEFAULT_OUTPUT_FORMAT,
)
ELEVENLABS_DEFAULT_LANGUAGE_CODE = os.environ.get(
    "ELEVENLABS_DEFAULT_LANGUAGE_CODE",
    ELEVENLABS_DEFAULT_LANGUAGE_CODE,
)
ELEVENLABS_DEFAULT_STABILITY = float(os.environ.get("ELEVENLABS_DEFAULT_STABILITY", ELEVENLABS_DEFAULT_STABILITY))
ELEVENLABS_DEFAULT_SIMILARITY_BOOST = float(
    os.environ.get("ELEVENLABS_DEFAULT_SIMILARITY_BOOST", ELEVENLABS_DEFAULT_SIMILARITY_BOOST)
)
ELEVENLABS_DEFAULT_STYLE = float(os.environ.get("ELEVENLABS_DEFAULT_STYLE", ELEVENLABS_DEFAULT_STYLE))
ELEVENLABS_DEFAULT_SPEED = float(os.environ.get("ELEVENLABS_DEFAULT_SPEED", ELEVENLABS_DEFAULT_SPEED))
ELEVENLABS_DEFAULT_USE_SPEAKER_BOOST = env_bool(
    "ELEVENLABS_DEFAULT_USE_SPEAKER_BOOST",
    ELEVENLABS_DEFAULT_USE_SPEAKER_BOOST,
)
ELEVENLABS_MAX_TEXT_LENGTH = int(os.environ.get("ELEVENLABS_MAX_TEXT_LENGTH", ELEVENLABS_MAX_TEXT_LENGTH))
ELEVENLABS_TIMEOUT_SECONDS = int(os.environ.get("ELEVENLABS_TIMEOUT_SECONDS", ELEVENLABS_TIMEOUT_SECONDS))
