import os
from pathlib import Path

from celery.schedules import crontab, schedule
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes"}
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "insecure-local-development-key"
    else:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in the environment.")
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "accounts",
    "farms",
    "weather",
    "alerts",
    "advice",
    "pests",
    "market",
    "academy",
    "waste",
    "gateway",
    "analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_DB_PATH", BASE_DIR / "db.sqlite3"),
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

LANGUAGE_CODE = "en"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOW_ALL_ORIGINS = os.environ.get("CORS_ALLOW_ALL_ORIGINS", "false").lower() in {
    "1",
    "true",
    "yes",
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Shamba API",
    "DESCRIPTION": "Agricultural services API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "SeverityLevel": "alerts.models.Rule.Severity",
        "NotificationChannel": "accounts.models.User.ChannelPreference",
    },
}

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_ALWAYS_EAGER = os.environ.get(
    "CELERY_TASK_ALWAYS_EAGER", "true" if DEBUG else "false"
).lower() in {"1", "true", "yes"}
CELERY_BEAT_SCHEDULE = {
    "refresh-ward-weather-every-six-hours": {
        "task": "weather.tasks.refresh_weather_snapshots",
        "schedule": schedule(run_every=6 * 60 * 60),
    },
    "evaluate-alert-rules-every-three-hours": {
        "task": "alerts.tasks.evaluate_alert_rules",
        "schedule": schedule(run_every=3 * 60 * 60),
    },
    "create-weekly-farmer-tip-drafts": {
        "task": "academy.tasks.send_weekly_tips",
        "schedule": crontab(minute=0, hour=9, day_of_week="1"),
    },
}
CELERY_TIMEZONE = TIME_ZONE
OPEN_METEO_TIMEOUT = int(os.environ.get("OPEN_METEO_TIMEOUT", "20"))
VENDEL_BASE_URL = os.environ.get("VENDEL_BASE_URL", "https://app.vendel.cc").rstrip("/")
VENDEL_API_KEY = os.environ.get("VENDEL_API_KEY", "")
VENDEL_WEBHOOK_SECRET = os.environ.get("VENDEL_WEBHOOK_SECRET", "")
SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "simulator").strip().lower()
if SMS_PROVIDER not in {"vendel", "simulator"}:
    raise ImproperlyConfigured("SMS_PROVIDER must be 'vendel' or 'simulator'.")
DEMO_RECIPIENTS = [
    number.strip()
    for number in os.environ.get("DEMO_RECIPIENTS", "").split(",")
    if number.strip()
]
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"sms_send": "5/min"}
