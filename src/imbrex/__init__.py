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
from imbrex._merge import MergeStrategy
from imbrex._priority import DEFAULT_PRIORITY

__all__ = [
    # Core
    "Config",
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

__version__ = "0.1.1"
