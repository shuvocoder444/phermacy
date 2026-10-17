import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-pharmacy-saas-bangladesh-super-secret-key-change-in-prod"

DEBUG = True

ALLOWED_HOSTS = ["*", "pos.webkoders.com", "195.250.26.201", "localhost", "127.0.0.1"]

CSRF_TRUSTED_ORIGINS = [
    "https://pos.webkoders.com",
    "http://pos.webkoders.com",
    "http://195.250.26.201",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # SaaS Apps
    "core",
    "inventory",
    "customers",
    "pos",
    "payments",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.TenantMiddleware",
]

ROOT_URLCONF = "pharmacy_saas.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.platform_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "pharmacy_saas.wsgi.application"
ASGI_APPLICATION = "pharmacy_saas.asgi.application"

# Database Configuration
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

import os
if os.path.exists("/home/webkoders/pos.webkoders.com"):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'webkoders_pos',
            'USER': 'webkoders_posstf',
            'PASSWORD': '5&EnaK4~Wm,~TYMb',
            'HOST': '127.0.0.1',
            'PORT': '5432',
        }
    }

# Cache Backend (Fast Local Memory Cache with Redis-ready structure)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "pharmaflow-cache",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Celery Configuration
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/2")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/3")
CELERY_TIMEZONE = "Asia/Dhaka"

# Internationalization & Bangladesh Timezone
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Bangladesh SMS Gateway Configuration
SMS_API_KEY = os.environ.get("SMS_API_KEY", "mock_key")
SMS_SENDER_ID = os.environ.get("SMS_SENDER_ID", "PHARMA")

SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SAMESITE = 'Lax'
