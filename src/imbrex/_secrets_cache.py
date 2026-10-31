"""Opt-in TTL cache for remote secret fetches (pure Python, no Pydantic)."""

from __future__ import annotations

import copy
import threading
from time import monotonic
from typing import Any

_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def get(key: str, ttl: float) -> dict[str, Any] | None:
    """Return a copy of the cached data for *key* if it is younger than *ttl*."""
    with _LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            return None
        stored_at, data = entry
        if monotonic() - stored_at >= ttl:
            del _CACHE[key]
            return None
        return copy.deepcopy(data)


def put(key: str, data: dict[str, Any]) -> None:
    """Store a copy of *data* under *key*."""
    with _LOCK:
        _CACHE[key] = (monotonic(), copy.deepcopy(data))


def clear_secrets_cache() -> None:
    """Forget every cached secret so the next load fetches fresh values."""
    with _LOCK:
        _CACHE.clear()
