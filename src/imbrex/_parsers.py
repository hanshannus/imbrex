"""
Low-level format parsers.

Each parser is a callable ``(source: str | bytes | Path) -> dict`` so they
compose cleanly without subclassing.  The :func:`parse_file` and
:func:`parse_string` helpers dispatch by extension / format tag.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from imbrex._exceptions import (
    ConfigFileNotFoundError,
    ConfigParseError,
    UnsupportedFormatError,
)

# ---------------------------------------------------------------------------
# Format registry
# ---------------------------------------------------------------------------

#: Canonical format name → file extensions (lowercase, with dot).
FORMAT_EXTENSIONS: dict[str, list[str]] = {
    "toml": [".toml"],
    "yaml": [".yaml", ".yml"],
    "json": [".json"],
}

#: Reverse map: extension → format name.
EXT_TO_FORMAT: dict[str, str] = {
    ext: fmt for fmt, exts in FORMAT_EXTENSIONS.items() for ext in exts
}

SUPPORTED_EXTENSIONS: list[str] = list(EXT_TO_FORMAT)
SUPPORTED_FORMATS: list[str] = list(FORMAT_EXTENSIONS)


def _fmt_from_path(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        return EXT_TO_FORMAT[ext]
    except KeyError:
        raise UnsupportedFormatError(ext, SUPPORTED_EXTENSIONS) from None


# ---------------------------------------------------------------------------
# Individual parsers
# ---------------------------------------------------------------------------


def _parse_toml(source: Path | str | bytes) -> dict[str, Any]:
    if isinstance(source, bytes):
        try:
            return tomllib.loads(source.decode())
        except tomllib.TOMLDecodeError as exc:
            raise ConfigParseError("<bytes>", exc) from exc

    path = Path(source)
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh) or {}
    except tomllib.TOMLDecodeError as exc:
        raise ConfigParseError(path, exc) from exc


def _parse_yaml(source: Path | str | bytes) -> dict[str, Any]:
    if isinstance(source, bytes):
        raw: str | bytes = source
    elif isinstance(source, str) and not Path(source).exists():
        # Treat plain string as YAML content, not a path
        raw = source
    else:
        path = Path(source)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigParseError(path, exc) from exc

    try:
        data = yaml.safe_load(raw)
        return data or {}
    except yaml.YAMLError as exc:
        raise ConfigParseError(str(source)[:80], exc) from exc


def _parse_json(source: Path | str | bytes) -> dict[str, Any]:
    if isinstance(source, bytes):
        text: str | bytes = source.decode()
    elif isinstance(source, str) and not Path(source).exists():
        text = source
    else:
        path = Path(source)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigParseError(path, exc) from exc

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise TypeError(f"Expected a JSON object, got {type(data).__name__}")
        return data
    except (json.JSONDecodeError, TypeError) as exc:
        raise ConfigParseError(str(source)[:80], exc) from exc


_PARSERS: dict[str, Any] = {
    "toml": _parse_toml,
    "yaml": _parse_yaml,
    "json": _parse_json,
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def parse_file(path: Path | str) -> dict[str, Any]:
    """Parse *path* according to its file extension."""
    p = Path(path)
    if not p.exists():
        raise ConfigFileNotFoundError(p)
    fmt = _fmt_from_path(p)
    parser: Callable[[Path | str | bytes], dict[str, Any]] = _PARSERS[fmt]
    return parser(p)


def parse_string(content: str, *, fmt: str) -> dict[str, Any]:
    """Parse a raw *content* string in the given *fmt* (``"toml"``, ``"yaml"``, ``"json"``)."""
    fmt = fmt.lower().strip(".")
    if fmt not in _PARSERS:
        raise UnsupportedFormatError(fmt, SUPPORTED_FORMATS)
    parser: Callable[[Path | str | bytes], dict[str, Any]] = _PARSERS[fmt]
    return parser(content.encode() if fmt == "toml" else content)


def parse_bytes(content: bytes, *, fmt: str) -> dict[str, Any]:
    """Parse raw *content* bytes in the given *fmt*."""
    fmt = fmt.lower().strip(".")
    if fmt not in _PARSERS:
        raise UnsupportedFormatError(fmt, SUPPORTED_FORMATS)
    parser: Callable[[Path | str | bytes], dict[str, Any]] = _PARSERS[fmt]
    return parser(content)


def discover_files(
    directory: Path,
    *,
    extension: str,
    recursive: bool = False,
) -> list[Path]:
    """Return all files in *directory* matching *extension*, sorted by name."""
    ext = extension if extension.startswith(".") else f".{extension}"
    glob = "**/*" if recursive else "*"
    return sorted(
        p for p in directory.glob(glob) if p.is_file() and p.suffix.lower() == ext
    )
