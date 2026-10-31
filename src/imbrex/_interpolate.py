"""``${...}`` interpolation of config values."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from imbrex._exceptions import ConfigInterpolationError
from imbrex._utils import _MISSING, _get_path

# "$${" is an escaped literal "${"; otherwise "${expr}".
_TOKEN = re.compile(r"\$\$\{|\$\{([^{}]*)\}")
_WHOLE = re.compile(r"\$\{([^{}]*)\}")


class Resolver:
    """Resolve references in values against *data* and *env*."""

    def __init__(self, data: dict[str, Any], env: Mapping[str, str]) -> None:
        self._data = data
        self._env = env

    def resolve(self, value: Any, where: str = "", *, lenient: bool = False) -> Any:
        """
        Return a copy of *value* with every ``${...}`` resolved.

        In *lenient* mode a string that cannot be resolved is kept as-is
        instead of raising (used for provenance layers, whose overridden
        values are allowed to reference things that do not exist).
        """
        return self._value(value, where, [], lenient)

    def _value(self, value: Any, where: str, stack: list[str], lenient: bool) -> Any:
        if isinstance(value, str):
            try:
                return self._string(value, where, stack)
            except ConfigInterpolationError:
                if lenient:
                    return value
                raise
        if isinstance(value, dict):
            return {
                k: self._value(v, f"{where}.{k}" if where else str(k), stack, lenient)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [
                self._value(v, f"{where}.{i}" if where else str(i), stack, lenient)
                for i, v in enumerate(value)
            ]
        return value

    def _string(self, text: str, where: str, stack: list[str]) -> Any:
        if "$" not in text:
            return text
        whole = _WHOLE.fullmatch(text)
        if whole:  # a lone reference keeps the referenced type
            return self._reference(whole.group(1), where, stack)

        def replace(m: re.Match[str]) -> str:
            if m.group(1) is None:
                return "${"
            return str(self._reference(m.group(1), where, stack))

        return _TOKEN.sub(replace, text)

    def _reference(self, expr: str, where: str, stack: list[str]) -> Any:
        name, has_default, default = expr.partition(":-")
        name = name.strip()

        if name.startswith("env:"):
            var = name[4:]
            if var in self._env:
                return self._env[var]
            if has_default:
                return default
            raise ConfigInterpolationError(
                expr, where, f"environment variable {var} is not set"
            )

        if name in stack:
            cycle = " -> ".join([*stack[stack.index(name) :], name])
            raise ConfigInterpolationError(expr, where, f"circular reference: {cycle}")
        found = _get_path(self._data, name, _MISSING)
        if found is _MISSING:
            if has_default:
                return default
            raise ConfigInterpolationError(expr, where, f"key {name!r} not found")
        return self._value(found, name, [*stack, name], False)
