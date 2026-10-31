"""Shared helpers for environment-style key/value sources."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

_INT = re.compile(r"-?(0|[1-9]\d*)")
_FLOAT = re.compile(r"-?(0|[1-9]\d*)\.\d+")


def coerce_value(raw: str) -> Any:
    """
    Convert a raw env string to ``bool``, ``int``, ``float`` or JSON.

    Anything that does not clearly look like one of those stays a ``str``
    (so ``007`` and ``1e3`` are left alone).
    """
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    if _INT.fullmatch(raw):
        return int(raw)
    if _FLOAT.fullmatch(raw):
        return float(raw)
    if raw[:1] in ("[", "{"):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


def nest_env(
    items: Mapping[str, str | None],
    prefix: str = "",
    *,
    separator: str = "__",
    coerce: bool = False,
) -> dict[str, Any]:
    """Turn ``PREFIX_A__B=1`` style pairs into ``{"a": {"b": 1}}``."""
    data: dict[str, Any] = {}
    prefix_upper = prefix.upper()

    for raw_key, value in items.items():
        if prefix_upper and not raw_key.upper().startswith(prefix_upper):
            continue
        stripped = raw_key[len(prefix) :] if prefix else raw_key
        parts = stripped.lower().split(separator.lower())
        node: dict[str, Any] = data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        text = value or ""
        node[parts[-1]] = coerce_value(text) if coerce else text

    return data
