"""Tests for Config freeze / unfreeze — immutable configuration instances."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from imbrex import Config, FrozenConfigError

# ── freeze() / unfreeze() / is_frozen ──────────────────────────────────────


class TestFreezeUnfreeze:
    def test_not_frozen_by_default(self) -> None:
        cfg = Config.from_dict({"key": "value"})
        assert cfg.is_frozen is False

    def test_freeze_method(self) -> None:
        cfg = Config.from_dict({"key": "value"})
        result = cfg.freeze()
        assert cfg.is_frozen is True
        assert result is cfg  # returns self for chaining

    def test_unfreeze_method(self) -> None:
        cfg = Config.from_dict({"key": "value"}).freeze()
        result = cfg.unfreeze()
        assert cfg.is_frozen is False
        assert result is cfg

    def test_freeze_unfreeze_roundtrip(self) -> None:
        cfg = Config.from_dict({"key": "value"})
        cfg.freeze()
        assert cfg.is_frozen is True
        cfg.unfreeze()
        assert cfg.is_frozen is False
        cfg.freeze()
        assert cfg.is_frozen is True

    def test_double_freeze_is_idempotent(self) -> None:
        cfg = Config.from_dict({"key": "value"}).freeze()
        cfg.freeze()  # should not raise
        assert cfg.is_frozen is True

    def test_double_unfreeze_is_idempotent(self) -> None:
        cfg = Config.from_dict({"key": "value"})
        cfg.unfreeze()  # already unfrozen — should not raise
        assert cfg.is_frozen is False


# ── freeze=True on factory classmethods ────────────────────────────────────


class TestFreezeOnFactories:
    def test_from_dict_freeze(self) -> None:
        cfg = Config.from_dict({"a": 1}, freeze=True)
        assert cfg.is_frozen is True
        assert cfg.get("a") == 1

    def test_from_string_freeze(self) -> None:
        cfg = Config.from_string("key: value\n", fmt="yaml", freeze=True)
        assert cfg.is_frozen is True
        assert cfg.get("key") == "value"

    def test_from_toml_freeze(self, tmp_path: Path) -> None:
        f = tmp_path / "a.toml"
        f.write_text('[app]\nname = "X"\n', encoding="utf-8")
        cfg = Config.from_toml(f, freeze=True)
        assert cfg.is_frozen is True
        assert cfg.get("app.name") == "X"

    def test_from_yaml_freeze(self, tmp_path: Path) -> None:
        f = tmp_path / "a.yaml"
        f.write_text("app:\n  name: X\n", encoding="utf-8")
        cfg = Config.from_yaml(f, freeze=True)
        assert cfg.is_frozen is True

    def test_from_json_freeze(self, tmp_path: Path) -> None:
        import json as _json

        f = tmp_path / "a.json"
        f.write_text(_json.dumps({"app": {"name": "X"}}), encoding="utf-8")
        cfg = Config.from_json(f, freeze=True)
        assert cfg.is_frozen is True

    def test_from_file_freeze(self, tmp_path: Path) -> None:
        f = tmp_path / "a.toml"
        f.write_text('[app]\nname = "X"\n', encoding="utf-8")
        cfg = Config.from_file(f, freeze=True)
        assert cfg.is_frozen is True

    def test_from_env_freeze(self) -> None:
        with patch.dict(os.environ, {"FRZTEST_KEY": "val"}, clear=False):
            cfg = Config.from_env(prefix="FRZTEST_", freeze=True)
        assert cfg.is_frozen is True
        assert cfg.get("key") == "val"

    def test_from_dir_freeze(self, tmp_path: Path) -> None:
        d = tmp_path / "conf"
        d.mkdir()
        (d / "defaults.toml").write_text('[app]\nname = "X"\n', encoding="utf-8")
        cfg = Config.from_dir(d, extension="toml", freeze=True)
        assert cfg.is_frozen is True
        assert cfg.get("app.name") == "X"

    def test_merge_freeze(self) -> None:
        c1 = Config.from_dict({"a": 1})
        c2 = Config.from_dict({"b": 2})
        merged = Config.merge(c1, c2, freeze=True)
        assert merged.is_frozen is True
        assert merged.get("a") == 1
        assert merged.get("b") == 2

    def test_from_dict_freeze_false_is_default(self) -> None:
        cfg = Config.from_dict({"a": 1}, freeze=False)
        assert cfg.is_frozen is False


# ── Frozen config blocks mutation ──────────────────────────────────────────


class TestFrozenBlocks:
    def test_override_raises_on_frozen(self) -> None:
        cfg = Config.from_dict({"app": {"debug": False}}, freeze=True)
        with pytest.raises(FrozenConfigError, match="override"):
            with cfg.override({"app.debug": True}):
                pass  # pragma: no cover

    def test_setattr_data_raises_on_frozen(self) -> None:
        cfg = Config.from_dict({"key": "value"}, freeze=True)
        with pytest.raises(FrozenConfigError, match="set _data"):
            cfg._data = {"new": "dict"}

    def test_setattr_sources_raises_on_frozen(self) -> None:
        cfg = Config.from_dict({"key": "value"}, freeze=True)
        with pytest.raises(FrozenConfigError, match="set _sources"):
            cfg._sources = ["hacked"]

    def test_frozen_config_error_is_imbrex_error(self) -> None:
        """FrozenConfigError should be catchable as ImbrexError."""
        from imbrex import ImbrexError

        cfg = Config.from_dict({"a": 1}, freeze=True)
        with pytest.raises(ImbrexError):
            with cfg.override({"a": 2}):
                pass  # pragma: no cover

    def test_frozen_config_error_is_attribute_error(self) -> None:
        """FrozenConfigError inherits from AttributeError for compatibility."""
        cfg = Config.from_dict({"a": 1}, freeze=True)
        with pytest.raises(AttributeError):
            cfg._data = {}


# ── Read access still works when frozen ────────────────────────────────────


class TestFrozenReadAccess:
    def test_get_works(self) -> None:
        cfg = Config.from_dict({"a": {"b": 1}}, freeze=True)
        assert cfg.get("a.b") == 1

    def test_getitem_works(self) -> None:
        cfg = Config.from_dict({"key": "val"}, freeze=True)
        assert cfg["key"] == "val"

    def test_contains_works(self) -> None:
        cfg = Config.from_dict({"key": "val"}, freeze=True)
        assert "key" in cfg
        assert "missing" not in cfg

    def test_len_works(self) -> None:
        cfg = Config.from_dict({"a": 1, "b": 2}, freeze=True)
        assert len(cfg) == 2

    def test_iter_works(self) -> None:
        cfg = Config.from_dict({"a": 1, "b": 2}, freeze=True)
        assert set(cfg) == {"a", "b"}

    def test_to_dict_works(self) -> None:
        cfg = Config.from_dict({"nested": {"key": "value"}}, freeze=True)
        d = cfg.to_dict()
        assert d == {"nested": {"key": "value"}}
        # mutating the copy does not affect cfg
        d["nested"]["key"] = "changed"
        assert cfg["nested"]["key"] == "value"

    def test_data_property_works(self) -> None:
        cfg = Config.from_dict({"x": 1}, freeze=True)
        assert cfg.data == {"x": 1}

    def test_sources_property_works(self) -> None:
        cfg = Config.from_dict({"x": 1}, freeze=True)
        assert cfg.sources == ["<dict:0>"]

    def test_repr_works(self) -> None:
        cfg = Config.from_dict({"a": 1}, freeze=True)
        r = repr(cfg)
        assert "Config" in r

    def test_eq_works(self) -> None:
        c1 = Config.from_dict({"a": 1}, freeze=True)
        c2 = Config.from_dict({"a": 1})
        assert c1 == c2

    def test_validate_works(self) -> None:
        from pydantic import BaseModel

        class Schema(BaseModel):
            key: str = "default"

        cfg = Config.from_dict({"key": "hello"}, freeze=True)
        result = cfg.validate(Schema)
        assert result.key == "hello"

    def test_get_missing_with_default(self) -> None:
        cfg = Config.from_dict({"a": 1}, freeze=True)
        assert cfg.get("missing", "fallback") == "fallback"

    def test_get_missing_raises_key_error(self) -> None:
        cfg = Config.from_dict({"a": 1}, freeze=True)
        with pytest.raises(KeyError):
            cfg.get("missing")


# ── Unfreeze then mutate ───────────────────────────────────────────────────


class TestUnfreezeThenMutate:
    def test_unfreeze_allows_override(self) -> None:
        cfg = Config.from_dict({"app": {"debug": False}}, freeze=True)
        cfg.unfreeze()
        with cfg.override({"app.debug": True}):
            assert cfg.get("app.debug") is True
        assert cfg.get("app.debug") is False

    def test_unfreeze_allows_setattr_data(self) -> None:
        cfg = Config.from_dict({"key": "value"}, freeze=True)
        cfg.unfreeze()
        cfg._data = {"new": "dict"}
        assert cfg["new"] == "dict"


# ── Chaining pattern ──────────────────────────────────────────────────────


class TestChainingPattern:
    def test_from_dict_then_freeze(self) -> None:
        cfg = Config.from_dict({"a": 1}).freeze()
        assert cfg.is_frozen is True
        assert cfg.get("a") == 1

    def test_freeze_returns_self(self) -> None:
        cfg = Config.from_dict({"a": 1})
        assert cfg.freeze() is cfg

    def test_unfreeze_returns_self(self) -> None:
        cfg = Config.from_dict({"a": 1}, freeze=True)
        assert cfg.unfreeze() is cfg
