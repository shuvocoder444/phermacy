import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Automatically load environment variables from .env if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    try:
        with open(env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k = _k.strip()
                    _v = _v.strip().strip("'\"")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass

DJANGO_ENV = os.environ.get("DJANGO_ENV", "").strip().lower()
HOSTED_APP_PATH = Path("/home/webkoders/pos.webkoders.com")
DEFAULT_DEBUG = DJANGO_ENV != "production" and not HOSTED_APP_PATH.exists()
DEBUG = os.environ.get("DJANGO_DEBUG", str(DEFAULT_DEBUG)).strip().lower() in ("1", "true", "yes")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip() or "local-development-only-change-me"

ALLOWED_HOSTS = [host.strip() for host in os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,pos.webkoders.com"
).split(",") if host.strip()]

CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()] or [
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

# Database Configuration: use PostgreSQL when DATABASE_URL is set; keep SQLite for local development.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    from urllib.parse import parse_qs, unquote, urlparse
    parsed_db = urlparse(DATABASE_URL)
    db_options = parse_qs(parsed_db.query)
    connection_options = {"connect_timeout": 5}
    if db_options.get("sslmode"):
        connection_options["sslmode"] = db_options["sslmode"][0]
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed_db.path.lstrip("/"),
        "USER": unquote(parsed_db.username or ""),
        "PASSWORD": unquote(parsed_db.password or ""),
        "HOST": parsed_db.hostname or "",
        "PORT": str(parsed_db.port or 5432),
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": connection_options,
    }}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
    }}
# Redis is shared across web workers for POS cart locks and cache. Local dev can keep DB cache.
REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {"default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "TIMEOUT": 86400,
    }}
else:
    CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "pos_cache_table",
        "TIMEOUT": 86400,
    }}

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "false").lower() in ("1", "true", "yes")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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
