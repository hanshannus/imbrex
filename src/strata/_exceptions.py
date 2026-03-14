"""Typed exception hierarchy for strata."""

from __future__ import annotations

from pathlib import Path


class StrataError(Exception):
    """Base class for all strata exceptions."""


class UnsupportedFormatError(StrataError):
    """Raised when a file extension or format string is not recognised."""

    def __init__(self, fmt: str, supported: list[str] | None = None) -> None:
        self.fmt = fmt
        tip = f"  Supported: {', '.join(supported)}" if supported else ""
        super().__init__(f"Unsupported format: {fmt!r}.{tip}")


class ConfigFileNotFoundError(StrataError, FileNotFoundError):
    """Raised when a required config file or directory is missing."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        super().__init__(f"Config path not found: {self.path}")


class ConfigParseError(StrataError):
    """Raised when a config file cannot be parsed."""

    def __init__(self, path: Path | str, cause: Exception) -> None:
        self.path = Path(path)
        self.cause = cause
        super().__init__(f"Failed to parse {self.path}: {cause}")


class ConfigValidationError(StrataError):
    """Raised when the merged config fails schema validation."""

    def __init__(self, cause: Exception, data: dict | None = None) -> None:
        self.cause = cause
        self.data = data
        super().__init__(f"Validation failed: {cause}")
