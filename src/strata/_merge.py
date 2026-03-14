"""
Deep-merge helpers built on top of ``mergedeep``.

``mergedeep`` handles recursive dict merging; this module adds:
- A :class:`MergeStrategy` enum that maps cleanly to ``mergedeep.Strategy``
- A per-key strategy override mechanism for fine-grained control
- A thin :func:`deep_merge` convenience wrapper

Strategies
----------
REPLACE (default)
    Scalars and lists from the higher-priority source unconditionally win.
ADDITIVE
    Lists are *concatenated*; scalars are replaced.
TYPESAFE
    Like REPLACE but raises :class:`TypeError` if two values have
    incompatible types (useful for catching config drift early).
"""

from __future__ import annotations

import copy
from enum import Enum
from typing import Any

from mergedeep import Strategy, merge


class MergeStrategy(str, Enum):
    """Deep-merge strategy for combining config layers."""

    REPLACE  = "replace"   #: Higher-priority values always win (lists replaced in full).
    ADDITIVE = "additive"  #: Lists concatenated; scalars replaced.
    TYPESAFE = "typesafe"  #: REPLACE, but raises TypeError on type mismatch.


def _to_mergedeep(strategy: MergeStrategy) -> Strategy:
    return Strategy.ADDITIVE if strategy is MergeStrategy.ADDITIVE else Strategy.REPLACE


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

    md_strat = _to_mergedeep(strategy)
    result: dict[str, Any] = {}
    for d in dicts:
        if key_strategies:
            result = _merge_with_overrides(result, d, key_strategies, md_strat)
        else:
            merge(result, d, strategy=md_strat)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _merge_with_overrides(
    base: dict[str, Any],
    override: dict[str, Any],
    key_strategies: dict[str, MergeStrategy],
    default_md_strategy: Strategy,
) -> dict[str, Any]:
    """Apply *override* onto *base*, then re-apply per-key additive logic."""
    result = copy.deepcopy(base)
    merge(result, override, strategy=default_md_strategy)

    for dotted, strat in key_strategies.items():
        if strat is not MergeStrategy.ADDITIVE:
            continue
        base_val  = _get_nested(base, dotted)
        over_val  = _get_nested(override, dotted)
        if isinstance(base_val, list) and isinstance(over_val, list):
            parts = dotted.split(".")
            node: Any = result
            for part in parts[:-1]:
                node = node[part]
            node[parts[-1]] = base_val + over_val

    return result


def _get_nested(data: dict[str, Any], dotted: str) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


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
