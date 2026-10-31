"""Small helpers around Django's cache for deterministic keys."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, TypeVar

from django.core.cache import cache

T = TypeVar("T")


def make_key(prefix: str, payload: Any) -> str:
    """Stable cache key from a JSON-serialisable payload (hashed to stay short)."""
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:32]
    return f"{prefix}:{digest}"


def get_or_set(key: str, ttl: int, producer: Callable[[], T]) -> T:
    """Return the cached value or compute, store and return it."""
    value = cache.get(key)
    if value is None:
        value = producer()
        if value is not None:
            cache.set(key, value, ttl)
    return value
