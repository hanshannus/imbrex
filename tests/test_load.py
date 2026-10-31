"""The one-call ``imbrex.load`` front door."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

import imbrex
from imbrex import Config, ConfigValidationError


class DB(BaseModel):
    url: str
    pool_size: int = 5


class Settings(BaseModel):
    debug: bool = False
    database: DB


@pytest.fixture
def cfg_dir(tmp_path: Path) -> Path:
    d = tmp_path / "config"
    d.mkdir()
    (d / "defaults.toml").write_text('[database]\nurl = "sqlite:///d"\n')
    (d / "production.toml").write_text("debug = false\n[database]\npool_size = 20\n")
    return d


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("APP_ENV", "ENV", "ENVIRONMENT"):
        monkeypatch.delenv(k, raising=False)


class TestLoad:
    def test_files_only(self, cfg_dir: Path) -> None:
        s = imbrex.load(Settings, cfg_dir, env="production", dotenv=None)
        assert s.database.url == "sqlite:///d"
        assert s.database.pool_size == 20

    def test_precedence_files_dotenv_env_overrides(
        self, cfg_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("APP_DATABASE__URL=pg://dotenv\nAPP_DEBUG=true\n")
        monkeypatch.setenv("APP_DATABASE__URL", "pg://env")
        s = imbrex.load(
            Settings,
            cfg_dir,
            env="production",
            env_prefix="APP_",
            dotenv=env_file,
            overrides={"database": {"pool_size": 1}},
        )
        assert s.database.url == "pg://env"  # env beats .env beats files
        assert s.debug is True  # coerced from .env
        assert s.database.pool_size == 1  # overrides beat everything

    def test_env_only_without_directory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_DATABASE__URL", "pg://x")
        s = imbrex.load(Settings, env_prefix="APP_", dotenv=None)
        assert s.database.url == "pg://x"

    def test_missing_dotenv_is_fine(self, cfg_dir: Path, tmp_path: Path) -> None:
        s = imbrex.load(Settings, cfg_dir, dotenv=tmp_path / "nope.env")
        assert s.database.url == "sqlite:///d"

    def test_validation_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigValidationError, match="database"):
            imbrex.load(Settings, env_prefix="NOPE_", dotenv=None)

    def test_autodetects_extension(self, tmp_path: Path) -> None:
        d = tmp_path / "c"
        d.mkdir()
        (d / "defaults.yaml").write_text("database:\n  url: y\n")
        assert imbrex.load(Settings, d, dotenv=None).database.url == "y"

    def test_ambiguous_extension_raises(self, tmp_path: Path) -> None:
        d = tmp_path / "c"
        d.mkdir()
        (d / "defaults.yaml").write_text("a: 1\n")
        (d / "local.toml").write_text("b = 1\n")
        with pytest.raises(imbrex.ImbrexError, match="extension"):
            imbrex.load(Settings, d, dotenv=None)

    def test_explicit_extension_with_mixed_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "c"
        d.mkdir()
        (d / "defaults.yaml").write_text("database:\n  url: y\n")
        (d / "local.toml").write_text("b = 1\n")
        s = imbrex.load(Settings, d, extension="yaml", dotenv=None)
        assert s.database.url == "y"


class TestLoadConfig:
    def test_returns_config_with_provenance(
        self, cfg_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_DATABASE__URL", "pg://env")
        cfg = imbrex.load_config(
            cfg_dir, env="production", env_prefix="APP_", dotenv=None
        )
        assert isinstance(cfg, Config)
        ex = cfg.explain("database.url")
        assert ex.value == "pg://env"
        assert ex.source.startswith("<env")
        assert ex.overridden[0][0].endswith("defaults.toml")


class TestEnvIsolation:
    def test_no_prefix_ignores_real_environment(
        self, cfg_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DATABASE__URL", "pg://leak")
        cfg = imbrex.load_config(cfg_dir, dotenv=None)
        assert cfg["database.url"] == "sqlite:///d"
        assert "path" not in cfg.to_dict()
