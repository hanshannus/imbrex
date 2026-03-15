"""Typed exception hierarchy for imbrex."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ImbrexError(Exception):
    """Base class for all imbrex exceptions."""


class UnsupportedFormatError(ImbrexError):
    """Raised when a file extension or format string is not recognised."""

    def __init__(self, fmt: str, supported: list[str] | None = None) -> None:
        self.fmt = fmt
        tip = f"  Supported: {', '.join(supported)}" if supported else ""
        super().__init__(f"Unsupported format: {fmt!r}.{tip}")


class ConfigFileNotFoundError(ImbrexError, FileNotFoundError):
    """Raised when a required config file or directory is missing."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        super().__init__(f"Config path not found: {self.path}")


class ConfigParseError(ImbrexError):
    """Raised when a config file cannot be parsed."""

    def __init__(self, path: Path | str, cause: Exception) -> None:
        self.path = Path(path)
        self.cause = cause
        super().__init__(f"Failed to parse {self.path}: {cause}")


class ConfigValidationError(ImbrexError):
    """Raised when the merged config fails schema validation."""

    def __init__(self, cause: Exception, data: dict[str, Any] | None = None) -> None:
        self.cause = cause
        self.data = data
        super().__init__(f"Validation failed: {cause}")


class ConfigSecretDescriptorError(ImbrexError):
    """Raised when a secrets descriptor file is invalid."""

    def __init__(self, path: Path | str, cause: Exception) -> None:
        self.path = Path(path)
        self.cause = cause
        super().__init__(f"Invalid secrets descriptor {self.path}: {cause}")


class SecretProviderError(ImbrexError):
    """Raised when a remote secret provider call fails."""

    def __init__(self, provider: str, cause: Exception) -> None:
        self.provider = provider
        self.cause = cause
        super().__init__(f"Secret provider '{provider}' failed: {cause}")


class FrozenConfigError(ImbrexError, AttributeError):
    """Raised when mutating a frozen Config instance."""

    def __init__(self, operation: str = "mutate") -> None:
        super().__init__(
            f"Cannot {operation} a frozen Config. "
            "Use .unfreeze() or create a new Config instead."
        )


