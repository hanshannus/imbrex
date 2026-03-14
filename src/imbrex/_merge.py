"""
Deep-merge helpers for combining configuration layers.

This module provides:
- A :class:`MergeStrategy` enum controlling how values combine
- A per-key strategy override mechanism for fine-grained control
- A :func:`deep_merge` convenience wrapper

Strategies
----------
REPLACE (default)
    Scalars and lists from the higher-priority source unconditionally win.
    Nested dicts are merged recursively.
ADDITIVE
    Lists are *concatenated*; scalars are replaced.  Nested dicts are
    merged recursively.
TYPESAFE
    Like REPLACE but raises :class:`TypeError` if two values have
    incompatible types (useful for catching config drift early).
"""

from __future__ import annotations

import copy
from enum import Enum
from typing import Any


class MergeStrategy(Enum):
    """Deep-merge strategy for combining config layers."""

    REPLACE = "replace"  #: Higher-priority values always win (lists replaced in full).
    ADDITIVE = "additive"  #: Lists concatenated; scalars replaced.
    TYPESAFE = "typesafe"  #: REPLACE, but raises TypeError on type mismatch.


# ---------------------------------------------------------------------------
# Core merge
# ---------------------------------------------------------------------------


def deep_merge(
    *dicts: dict[str, Any],
    strategy: MergeStrategy = MergeStrategy.REPLACE,
    key_strategies: dict[str, MergeStrategy] | None = None,
) -> dict[str, Any]:
    """
    Merge *dicts* left-to-right (rightmost wins) and return a new dict.

    Parameters
    ----------
    *dicts:
        Two or more dicts to merge in order.  The *last* dict has the
        highest priority (its values override all previous ones).
    strategy:
        Default merge strategy for every key.
    key_strategies:
        Per-key overrides keyed by dot-separated paths, e.g.
        ``{"server.allowed_hosts": MergeStrategy.ADDITIVE}``.

    """
    if not dicts:
        return {}

    if strategy is MergeStrategy.TYPESAFE:
        return _typesafe_merge(*dicts)

    result: dict[str, Any] = {}
    for d in dicts:
        result = _recursive_merge(result, d, strategy, key_strategies)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _recursive_merge(
    base: dict[str, Any],
    override: dict[str, Any],
    strategy: MergeStrategy,
    key_strategies: dict[str, MergeStrategy] | None,
    _prefix: str = "",
) -> dict[str, Any]:
    """Recursively merge *override* into a deep copy of *base*."""
    result = copy.deepcopy(base)

    for key, value in override.items():
        cur_path = f"{_prefix}.{key}" if _prefix else key

        # Determine the effective strategy for this key.
        effective = (
            key_strategies.get(cur_path, strategy) if key_strategies else strategy
        )

        existing = result.get(key)

        if isinstance(existing, dict) and isinstance(value, dict):
            # Both sides are dicts — recurse.
            result[key] = _recursive_merge(
                existing,
                value,
                strategy,
                key_strategies,
                _prefix=cur_path,
            )
        elif (
            effective is MergeStrategy.ADDITIVE
            and isinstance(existing, list)
            and isinstance(value, list)
        ):
            # Additive: concatenate lists.
            result[key] = existing + value
        else:
            # Replace (or additive on non-list): override wins.
            result[key] = copy.deepcopy(value)

    return result


def _typesafe_merge(*dicts: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for d in dicts:
        result = _typesafe_layer(result, d)
    return result


def _typesafe_layer(
    base: dict[str, Any],
    override: dict[str, Any],
    _path: str = "",
) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        cur_path = f"{_path}.{key}" if _path else key
        existing = result.get(key)
        if existing is not None and not isinstance(value, type(existing)):
            raise TypeError(
                f"Type mismatch at {cur_path!r}: "
                f"existing={type(existing).__name__}, incoming={type(value).__name__}"
            )
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = _typesafe_layer(existing, value, _path=cur_path)
        else:
            result[key] = value
    return result
