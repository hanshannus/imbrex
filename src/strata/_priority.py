"""
Hierarchical priority ordering for configuration files.

Files loaded from a directory are sorted by a well-known priority table so
that settings cascade naturally:

    defaults → base → development → staging → production → local → secrets

A file whose stem is not in the table receives priority 0 and is therefore
loaded *before* every named tier — it can be overridden by anything.

The active environment is resolved (in order) from:
  1. The ``env`` argument passed to :func:`sort_paths`.
  2. The ``APP_ENV`` environment variable.
  3. The ``ENV`` environment variable.
  4. The ``ENVIRONMENT`` environment variable.
"""

from __future__ import annotations

import os
import re
import fnmatch
from pathlib import Path

# ---------------------------------------------------------------------------
# Built-in priority table
# ---------------------------------------------------------------------------

#: Mapping of filename stem → integer priority (higher = applied later = wins).
DEFAULT_PRIORITY: dict[str, int] = {
    "defaults":    100,
    "default":     100,
    "base":        200,
    "common":      200,
    "shared":      200,
    "development": 300,
    "dev":         300,
    "testing":     400,
    "test":        400,
    "staging":     400,
    "production":  500,
    "prod":        500,
    "local":       600,
    "secrets":     700,
    "secret":      700,
}

#: Priority assigned to the active environment file when its stem is not
#: explicitly listed in the table (slots between "base" and "local").
_UNKNOWN_ENV_PRIORITY: int = 350


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_env() -> str | None:
    """Read the active environment name from process environment variables."""
    return (
        os.environ.get("APP_ENV")
        or os.environ.get("ENV")
        or os.environ.get("ENVIRONMENT")
    )


def _stem_priority(
    stem: str,
    table: dict[str, int],
    active_env: str | None,
) -> int:
    """Return the priority for *stem*, honouring *active_env* and pattern matching."""
    s = stem.lower()

    # If this stem IS the active environment, use its table entry (or fallback)
    if active_env and s == active_env.lower():
        return table.get(s, _UNKNOWN_ENV_PRIORITY)

    # 1. Exact match
    if s in table:
        return table[s]

    # 2. Glob / regex patterns in the table
    for pattern, prio in table.items():
        if pattern.startswith('r"') or pattern.startswith("r'"):
            if re.fullmatch(pattern[2:-1], s):
                return prio
        elif any(c in pattern for c in ("*", "?", "[")):
            if fnmatch.fnmatch(s, pattern):
                return prio

    return 0  # unknown → loaded first, overridable by everything


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sort_paths(
    paths: list[Path],
    *,
    env: str | None = None,
    priority_table: dict[str, int] | None = None,
    max_env_priority: bool = True,
) -> list[Path]:
    """
    Return *paths* sorted from lowest → highest priority (i.e. the correct
    load order so that later files override earlier ones).

    Parameters
    ----------
    paths:
        Unsorted list of config file paths (any format).
    env:
        Active environment name.  When given, files whose stem is *strictly
        higher* than the env's priority are excluded so that loading with
        ``env="development"`` never silently applies ``production.toml``.
        Pass ``None`` to disable filtering and load every file found.
    priority_table:
        Custom priority mapping.  Merged on top of :data:`DEFAULT_PRIORITY`
        so you only need to supply the entries you want to change.
    max_env_priority:
        When *True* (default), exclude files that outrank the active env.
    """
    table: dict[str, int] = {**DEFAULT_PRIORITY, **(priority_table or {})}
    active_env = (env or _resolve_env() or "").lower() or None

    env_ceiling: int | None = None
    if active_env and max_env_priority:
        env_ceiling = _stem_priority(active_env, table, active_env)

    result: list[Path] = []
    for p in paths:
        prio = _stem_priority(p.stem, table, active_env)
        if env_ceiling is not None and prio > env_ceiling:
            continue
        result.append(p)

    return sorted(result, key=lambda p: _stem_priority(p.stem, table, active_env))


def priority_of(
    stem: str,
    *,
    env: str | None = None,
    priority_table: dict[str, int] | None = None,
) -> int:
    """Return the numeric priority for a file stem (useful for debugging)."""
    table = {**DEFAULT_PRIORITY, **(priority_table or {})}
    active_env = (env or _resolve_env() or "").lower() or None
    return _stem_priority(stem, table, active_env)
