"""Settings for the pytest run: deterministic, no secrets required."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ["REDIS_URL"] = ""

from .settings import *  # noqa: E402,F403

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
ORS_API_KEY = ""
HTTP_RETRIES = 0
