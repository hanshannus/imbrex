"""Provenance report for a single config key."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from imbrex._redact import REDACTED, is_sensitive


@dataclass(frozen=True)
class Explanation:
    """
    Where a config value came from.

    ``source`` is the layer whose value won; ``overridden`` lists the earlier
    layers that also defined the key, lowest priority first.  Values under
    sensitive-looking keys are masked.
    """

    path: str
    value: Any
    source: str
    overridden: list[tuple[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [f"{self.path} = {self.value!r}", f"  from {self.source}"]
        lines += [f"  overrides {src}: {val!r}" for src, val in self.overridden]
        return "\n".join(lines)


def build_explanation(path: str, hits: list[tuple[str, Any]]) -> Explanation:
    """Build an :class:`Explanation` from ``(source, value)`` hits, low → high."""
    mask = any(is_sensitive(part) for part in path.split("."))
    shown = [(src, REDACTED if mask else val) for src, val in hits]
    (source, value), earlier = shown[-1], shown[:-1]
    return Explanation(path, value, source, earlier)
