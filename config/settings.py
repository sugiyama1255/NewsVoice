"""Django全体設定。

共通設定をここに置き、APIキーなど環境ごとに変える値は末尾で読み込む
config/settings_local.py で上書きします。
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-_5@wk&=$g1l3*e2s8!$aa!#^w5k!cwogg_kx-x)k*^(sh-_(72'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "testserver",
]

# 外部APIの初期値。秘密値は settings_local.py にだけ置きます。
GEMINI_API_KEY = ""
GEMINI_MODEL = "gemini-2.5-flash-lite"
GDELT_API_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_SORT = "datedesc"
GDELT_MAX_RETRIES = 2
GDELT_RETRY_WAIT_SECONDS = 6
GDELT_MIN_REQUEST_INTERVAL_SECONDS = 6
NEWSVOICE_TTS_ENABLED = True
NEWSVOICE_SIMPLE_TTS_ENABLED = True
NEWSVOICE_HIGH_QUALITY_TTS_ENABLED = False
NEWSVOICE_DEFAULT_TTS_PROVIDER = "voicevox"
NEWSVOICE_DEFAULT_VOICE_NAME = ""
NEWSVOICE_AUDIO_FORMAT = "mp3"
NEWSVOICE_AUDIO_DIR = "newsvoice/audio"
NEWSVOICE_TTS_MAX_TEXT_LENGTH = 1200


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'newsvoice',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'ja'

TIME_ZONE = 'Asia/Tokyo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "newsvoice_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "newsvoice.log",
            "maxBytes": 1024 * 1024,
            "backupCount": 5,
            "formatter": "standard",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "newsvoice": {
            "handlers": ["console", "newsvoice_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# 環境固有設定を最後に読み込み、上の初期値を上書きできるようにします。
try:
    from .settings_local import *
except ImportError:
    pass
