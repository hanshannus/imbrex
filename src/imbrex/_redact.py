"""Masking of sensitive values for display, errors and exports."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "***"

_SENSITIVE = re.compile(
    r"password|passwd|pwd|secret|token|api[_-]?key|private[_-]?key|credential",
    re.IGNORECASE,
)


def is_sensitive(key: object) -> bool:
    """Return ``True`` when *key* looks like it names a secret value."""
    return isinstance(key, str) and _SENSITIVE.search(key) is not None


def redact(value: Any) -> Any:
    """
    Return a deep copy of *value* with sensitive entries replaced by ``***``.

    A mapping entry is masked, whole, when its key looks sensitive (e.g.
    ``password``, ``api_token``, ``client_secret``).  The input is never
    mutated.
    """
    if isinstance(value, dict):
        return {k: REDACTED if is_sensitive(k) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value
