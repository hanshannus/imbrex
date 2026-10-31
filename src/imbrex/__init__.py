"""
imbrex — Hierarchical configuration management for Python.

Load YAML, TOML, and JSON files individually or from a directory, merge them
in the correct priority order, and validate the result with Pydantic.

Quick start::

    from imbrex import Config

    # Single file
    cfg = Config.from_toml("settings.toml")

    # Multiple files (merged left-to-right, last file wins)
    cfg = Config.from_toml("defaults.toml", "production.toml")

    # Entire directory, auto-sorted by environment tier
    cfg = Config.from_dir("config/", extension="toml", env="production")

    # Validate with a Pydantic model
    from pydantic import BaseModel


    class AppSettings(BaseModel):
        debug: bool = False
        database_url: str = "sqlite:///app.db"


    settings = cfg.validate(AppSettings)
    print(settings.database_url)
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from imbrex._config import Config
from imbrex._exceptions import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigSecretDescriptorError,
    ConfigValidationError,
    FrozenConfigError,
    ImbrexError,
    SecretProviderError,
    UnsupportedFormatError,
)
from imbrex._explain import Explanation
from imbrex._load import load, load_config
from imbrex._merge import MergeStrategy
from imbrex._priority import DEFAULT_PRIORITY

__all__ = [
    # Core
    "Config",
    "load",
    "load_config",
    "Explanation",
    # Merge
    "MergeStrategy",
    # Priority
    "DEFAULT_PRIORITY",
    # Exceptions
    "ImbrexError",
    "ConfigFileNotFoundError",
    "ConfigParseError",
    "ConfigSecretDescriptorError",
    "ConfigValidationError",
    "FrozenConfigError",
    "SecretProviderError",
    "UnsupportedFormatError",
]

try:
    __version__ = _pkg_version("imbrex")
except PackageNotFoundError:  # pragma: no cover - running from a bare checkout
    __version__ = "0+unknown"
