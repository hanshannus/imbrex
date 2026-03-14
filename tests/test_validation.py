"""Tests for Config.validate — Pydantic schema validation."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field

from strata import Config
from strata._exceptions import ConfigValidationError


# ── Pydantic models used in tests ──────────────────────────────────────────


class DatabaseSettings(BaseModel):
    url: str
    pool_size: int = 5
    echo: bool = False


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    allowed_hosts: list[str] = Field(default_factory=list)


class AppSettings(BaseModel):
    app: dict[str, Any] = Field(default_factory=dict)
    database: DatabaseSettings
    server: ServerSettings = Field(default_factory=ServerSettings)
    logging: dict[str, Any] = Field(default_factory=dict)


class SimpleModel(BaseModel):
    name: str
    debug: bool = False
    workers: int = 1


# ── Happy-path validation ─────────────────────────────────────────────────


class TestValidateSuccess:
    def test_simple_model(self) -> None:
        cfg = Config.from_dict({"name": "TestApp", "debug": True, "workers": 4})
        settings = cfg.validate(SimpleModel)
        assert isinstance(settings, SimpleModel)
        assert settings.name == "TestApp"
        assert settings.debug is True
        assert settings.workers == 4

    def test_defaults_filled(self) -> None:
        cfg = Config.from_dict({"name": "TestApp"})
        settings = cfg.validate(SimpleModel)
        assert settings.debug is False
        assert settings.workers == 1

    def test_nested_model(self) -> None:
        data = {
            "app": {"name": "Nested"},
            "database": {"url": "sqlite:///x.db", "pool_size": 10},
            "server": {"host": "0.0.0.0", "port": 80},
        }
        cfg = Config.from_dict(data)
        settings = cfg.validate(AppSettings)
        assert settings.database.url == "sqlite:///x.db"
        assert settings.database.pool_size == 10
        assert settings.server.host == "0.0.0.0"

    def test_validate_from_file(self, config_dir) -> None:  # type: ignore[no-untyped-def]
        cfg = Config.from_dir(config_dir, extension="toml", env="development")
        settings = cfg.validate(AppSettings)
        assert settings.database.url == "postgresql://localhost/myapp_dev"
        assert settings.app["debug"] is True

    def test_extra_keys_ignored_by_default(self) -> None:
        cfg = Config.from_dict({"name": "X", "unknown_field": 123})
        settings = cfg.validate(SimpleModel)
        assert settings.name == "X"


# ── Validation failures ───────────────────────────────────────────────────


class TestValidateFailure:
    def test_missing_required_field(self) -> None:
        cfg = Config.from_dict({"debug": True})
        with pytest.raises(ConfigValidationError):
            cfg.validate(SimpleModel)

    def test_wrong_type(self) -> None:
        cfg = Config.from_dict({"name": "X", "workers": "not-a-number"})
        with pytest.raises(ConfigValidationError):
            cfg.validate(SimpleModel)

    def test_nested_missing_required(self) -> None:
        # database requires 'url'
        cfg = Config.from_dict({"database": {"pool_size": 5}})
        with pytest.raises(ConfigValidationError):
            cfg.validate(AppSettings)

    def test_error_contains_data(self) -> None:
        cfg = Config.from_dict({"debug": True})
        with pytest.raises(ConfigValidationError) as exc_info:
            cfg.validate(SimpleModel)
        assert exc_info.value.data is not None


# ── Strict model validation ───────────────────────────────────────────────


class StrictModel(BaseModel):
    model_config = {"extra": "forbid"}
    name: str


class TestValidateStrict:
    def test_extra_fields_forbidden(self) -> None:
        cfg = Config.from_dict({"name": "X", "extra": "not allowed"})
        with pytest.raises(ConfigValidationError):
            cfg.validate(StrictModel)

    def test_valid_strict(self) -> None:
        cfg = Config.from_dict({"name": "X"})
        settings = cfg.validate(StrictModel)
        assert settings.name == "X"


# ── Validate returns correct type ─────────────────────────────────────────


class TestValidateType:
    def test_return_type(self) -> None:
        cfg = Config.from_dict({"name": "X"})
        result = cfg.validate(SimpleModel)
        assert type(result) is SimpleModel

    def test_nested_return_type(self) -> None:
        data = {
            "database": {"url": "sqlite:///x.db"},
        }
        cfg = Config.from_dict(data)
        result = cfg.validate(AppSettings)
        assert type(result) is AppSettings
        assert type(result.database) is DatabaseSettings

