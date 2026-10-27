import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-insecure-secret")

from .settings import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
