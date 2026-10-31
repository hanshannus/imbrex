"""Attribute access and provenance (``explain``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from imbrex import Config


@pytest.fixture
def layered(tmp_path: Path) -> Config:
    (tmp_path / "defaults.toml").write_text(
        '[database]\nurl = "sqlite:///d"\npool = 5\npassword = "pw0"\n'
    )
    (tmp_path / "production.toml").write_text(
        '[database]\nurl = "pg://prod"\npassword = "pw1"\n'
    )
    return Config.from_dir(tmp_path, env="production")


class TestAttributeAccess:
    def test_nested(self) -> None:
        cfg = Config.from_dict({"database": {"url": "x", "pool": 5}})
        assert cfg.database.url == "x"
        assert cfg.database.pool == 5

    def test_missing_raises_attribute_error(self) -> None:
        cfg = Config.from_dict({"a": 1})
        with pytest.raises(AttributeError, match="nope"):
            _ = cfg.nope

    def test_subtree_is_frozen_config(self) -> None:
        cfg = Config.from_dict({"database": {"url": "x"}})
        sub = cfg.database
        assert isinstance(sub, Config)
        assert sub.is_frozen
        assert sub["url"] == "x"

    def test_lists_returned_raw(self) -> None:
        cfg = Config.from_dict({"hosts": ["a", "b"]})
        assert cfg.hosts == ["a", "b"]

    def test_methods_win_over_keys(self) -> None:
        cfg = Config.from_dict({"get": 1})
        assert callable(cfg.get)
        assert cfg["get"] == 1

    def test_private_names_not_proxied(self) -> None:
        with pytest.raises(AttributeError):
            _ = Config.from_dict({"_x": 1})._x


class TestExplain:
    def test_winning_source_and_overridden(self, layered: Config) -> None:
        ex = layered.explain("database.url")
        assert ex.value == "pg://prod"
        assert ex.source.endswith("production.toml")
        assert len(ex.overridden) == 1
        src, val = ex.overridden[0]
        assert src.endswith("defaults.toml")
        assert val == "sqlite:///d"

    def test_only_in_one_layer(self, layered: Config) -> None:
        ex = layered.explain("database.pool")
        assert ex.value == 5
        assert ex.source.endswith("defaults.toml")
        assert ex.overridden == []

    def test_sensitive_values_masked(self, layered: Config) -> None:
        ex = layered.explain("database.password")
        assert ex.value == "***"
        assert all(v == "***" for _, v in ex.overridden)
        assert "pw1" not in str(ex)
        assert "pw0" not in str(ex)

    def test_str_is_readable(self, layered: Config) -> None:
        text = str(layered.explain("database.url"))
        assert "database.url" in text
        assert "production.toml" in text
        assert "defaults.toml" in text

    def test_missing_key(self, layered: Config) -> None:
        with pytest.raises(KeyError):
            layered.explain("nope.nope")

    def test_merge_keeps_layers(self) -> None:
        a = Config.from_dict({"x": 1})
        b = Config.from_dict({"x": 2})
        ex = Config.merge(a, b).explain("x")
        assert ex.value == 2
        assert ex.overridden == [("<dict:0>", 1)]

    def test_env_and_dotenv_sources(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        f = tmp_path / ".env"
        f.write_text("APP_PORT=1\n")
        monkeypatch.setenv("APP_PORT", "2")
        cfg = Config.merge(Config.from_dotenv(f, "APP_"), Config.from_env("APP_"))
        ex = cfg.explain("port")
        assert ex.value == "2"
        assert ex.source.startswith("<env")
        assert ex.overridden[0][0] == str(f)

    def test_subtree_explain_is_relative(self, layered: Config) -> None:
        ex = layered.database.explain("url")
        assert ex.value == "pg://prod"
        assert ex.source.endswith("production.toml")
