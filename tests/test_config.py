"""Tests for strata._config.Config — loaders, dict-like access, merge, repr."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from strata import Config, MergeStrategy
from strata._exceptions import (
    ConfigFileNotFoundError,
    UnsupportedFormatError,
)

# ── from_toml ──────────────────────────────────────────────────────────────


class TestFromTOML:
    def test_single_file(self, toml_file: Path) -> None:
        cfg = Config.from_toml(toml_file)
        assert cfg["app"]["name"] == "TestApp"
        assert cfg["database"]["pool_size"] == 5

    def test_multiple_files_merge(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.toml"
        f2 = tmp_path / "b.toml"
        f1.write_text('[app]\nname = "A"\nworkers = 1\n', encoding="utf-8")
        f2.write_text('[app]\nname = "B"\n', encoding="utf-8")
        cfg = Config.from_toml(f1, f2)
        assert cfg["app"]["name"] == "B"  # b overrides
        assert cfg["app"]["workers"] == 1  # kept from a

    def test_sources_tracked(self, toml_file: Path) -> None:
        cfg = Config.from_toml(toml_file)
        assert len(cfg.sources) == 1
        assert "settings.toml" in cfg.sources[0]

    def test_empty_args_returns_empty_config(self) -> None:
        cfg = Config.from_toml()
        assert cfg.data == {}
        assert cfg.sources == []


# ── from_yaml ──────────────────────────────────────────────────────────────


class TestFromYAML:
    def test_single_file(self, yaml_file: Path) -> None:
        cfg = Config.from_yaml(yaml_file)
        assert cfg["app"]["name"] == "TestApp"

    def test_multiple_files_merge(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.yaml"
        f2 = tmp_path / "b.yaml"
        f1.write_text("app:\n  name: A\n  workers: 1\n", encoding="utf-8")
        f2.write_text("app:\n  name: B\n", encoding="utf-8")
        cfg = Config.from_yaml(f1, f2)
        assert cfg["app"]["name"] == "B"
        assert cfg["app"]["workers"] == 1


# ── from_json ──────────────────────────────────────────────────────────────


class TestFromJSON:
    def test_single_file(self, json_file: Path) -> None:
        cfg = Config.from_json(json_file)
        assert cfg["app"]["name"] == "TestApp"
        assert cfg["database"]["pool_size"] == 5

    def test_multiple_files_merge(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.json"
        f2 = tmp_path / "b.json"
        f1.write_text(
            json.dumps({"app": {"name": "A", "workers": 1}}), encoding="utf-8"
        )
        f2.write_text(json.dumps({"app": {"name": "B"}}), encoding="utf-8")
        cfg = Config.from_json(f1, f2)
        assert cfg["app"]["name"] == "B"
        assert cfg["app"]["workers"] == 1


# ── from_file ──────────────────────────────────────────────────────────────


class TestFromFile:
    def test_toml_via_from_file(self, toml_file: Path) -> None:
        cfg = Config.from_file(toml_file)
        assert cfg["app"]["name"] == "TestApp"

    def test_yaml_via_from_file(self, yaml_file: Path) -> None:
        cfg = Config.from_file(yaml_file)
        assert cfg["app"]["name"] == "TestApp"

    def test_json_via_from_file(self, json_file: Path) -> None:
        cfg = Config.from_file(json_file)
        assert cfg["app"]["name"] == "TestApp"

    def test_missing_file_raises(self) -> None:
        with pytest.raises(ConfigFileNotFoundError):
            Config.from_file("/nope.toml")


# ── from_dir ───────────────────────────────────────────────────────────────


class TestFromDir:
    def test_loads_all_files(self, config_dir: Path) -> None:
        cfg = Config.from_dir(config_dir, extension="toml")
        assert "app" in cfg
        assert len(cfg.sources) >= 2

    def test_env_development(self, config_dir: Path) -> None:
        cfg = Config.from_dir(config_dir, extension="toml", env="development")
        assert cfg["app"]["debug"] is True
        assert cfg["app"]["workers"] == 1
        # production values should NOT be present
        assert cfg["database"]["url"] == "postgresql://localhost/myapp_dev"

    def test_env_production(self, config_dir: Path) -> None:
        cfg = Config.from_dir(config_dir, extension="toml", env="production")
        assert cfg["app"]["debug"] is False
        assert cfg["app"]["workers"] == 8
        assert cfg["database"]["pool_size"] == 20

    def test_explicit_order(self, config_dir: Path) -> None:
        cfg = Config.from_dir(
            config_dir,
            extension="toml",
            order=["defaults", "production"],
        )
        assert cfg["app"]["debug"] is False
        assert cfg["database"]["url"] == "postgresql://prod-db:5432/myapp"

    def test_explicit_order_skips_missing_stems(self, config_dir: Path) -> None:
        cfg = Config.from_dir(
            config_dir,
            extension="toml",
            order=["defaults", "nonexistent"],
        )
        assert cfg["app"]["name"] == "MyApp"

    def test_missing_dir_raises(self) -> None:
        with pytest.raises(ConfigFileNotFoundError):
            Config.from_dir("/does/not/exist", extension="toml")

    def test_not_a_directory_raises(self, toml_file: Path) -> None:
        with pytest.raises(NotADirectoryError):
            Config.from_dir(toml_file, extension="toml")

    def test_recursive(self, tmp_path: Path) -> None:
        d = tmp_path / "conf"
        sub = d / "sub"
        sub.mkdir(parents=True)
        (d / "defaults.toml").write_text('[app]\nname = "Top"\n', encoding="utf-8")
        (sub / "extra.toml").write_text("[app]\nextra = true\n", encoding="utf-8")
        cfg = Config.from_dir(d, extension="toml", recursive=True)
        assert cfg["app"]["extra"] is True

    def test_yaml_dir(self, yaml_config_dir: Path) -> None:
        cfg = Config.from_dir(yaml_config_dir, extension="yaml", env="development")
        assert cfg["app"]["debug"] is True
        assert cfg["database"]["url"] == "postgresql://localhost/dev"

    def test_key_strategies_with_dir(self, config_dir: Path) -> None:
        cfg = Config.from_dir(
            config_dir,
            extension="toml",
            env="production",
            key_strategies={"server.allowed_hosts": MergeStrategy.ADDITIVE},
        )
        # defaults has ["localhost"], production has ["myapp.com", "www.myapp.com"]
        hosts = cfg["server"]["allowed_hosts"]
        assert "localhost" in hosts
        assert "myapp.com" in hosts


# ── from_dict ──────────────────────────────────────────────────────────────


class TestFromDict:
    def test_single_dict(self) -> None:
        cfg = Config.from_dict({"key": "value"})
        assert cfg["key"] == "value"

    def test_multiple_dicts_merge(self) -> None:
        cfg = Config.from_dict(
            {"db": {"url": "a", "pool": 5}},
            {"db": {"url": "b"}},
        )
        assert cfg["db"]["url"] == "b"
        assert cfg["db"]["pool"] == 5

    def test_sources_are_tagged(self) -> None:
        cfg = Config.from_dict({"a": 1}, {"b": 2})
        assert cfg.sources == ["<dict:0>", "<dict:1>"]

    def test_merge_strategy(self) -> None:
        cfg = Config.from_dict(
            {"hosts": ["a"]},
            {"hosts": ["b"]},
            merge_strategy=MergeStrategy.ADDITIVE,
        )
        assert cfg["hosts"] == ["a", "b"]


# ── from_string ────────────────────────────────────────────────────────────


class TestFromString:
    def test_toml_string(self) -> None:
        cfg = Config.from_string('[db]\nurl = "sqlite:///x"\n', fmt="toml")
        assert cfg["db"]["url"] == "sqlite:///x"

    def test_yaml_string(self) -> None:
        cfg = Config.from_string("db:\n  url: sqlite:///x\n", fmt="yaml")
        assert cfg["db"]["url"] == "sqlite:///x"

    def test_json_string(self) -> None:
        cfg = Config.from_string('{"db": {"url": "sqlite:///x"}}', fmt="json")
        assert cfg["db"]["url"] == "sqlite:///x"

    def test_unsupported_format_raises(self) -> None:
        with pytest.raises(UnsupportedFormatError):
            Config.from_string("data", fmt="xml")

    def test_sources_tagged(self) -> None:
        cfg = Config.from_string("key: value\n", fmt="yaml")
        assert cfg.sources == ["<string:yaml>"]


# ── from_env ───────────────────────────────────────────────────────────────


class TestFromEnv:
    def test_basic_env_vars(self) -> None:
        env = {
            "MYAPP_DATABASE__URL": "pg://host/db",
            "MYAPP_DATABASE__POOL_SIZE": "10",
            "MYAPP_DEBUG": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = Config.from_env(prefix="MYAPP_")
        assert cfg["database"]["url"] == "pg://host/db"
        assert cfg["database"]["pool_size"] == "10"
        assert cfg["debug"] == "true"

    def test_prefix_stripped(self) -> None:
        with patch.dict(os.environ, {"TEST_KEY": "val"}, clear=False):
            cfg = Config.from_env(prefix="TEST_")
        assert cfg["key"] == "val"

    def test_no_prefix(self) -> None:
        with patch.dict(os.environ, {"SOME_UNIQUE_KEY_XYZ": "abc"}, clear=False):
            cfg = Config.from_env(prefix="")
        assert cfg["some_unique_key_xyz"] == "abc"

    def test_custom_separator(self) -> None:
        env = {"PFX_A_B_C": "val"}
        with patch.dict(os.environ, env, clear=False):
            cfg = Config.from_env(prefix="PFX_", separator="_")
        assert cfg["a"]["b"]["c"] == "val"

    def test_source_tagged(self) -> None:
        cfg = Config.from_env(prefix="NOEXIST_XYZ_")
        assert "<env" in cfg.sources[0]


# ── Config.merge ───────────────────────────────────────────────────────────


class TestConfigMerge:
    def test_merge_two_configs(self) -> None:
        c1 = Config.from_dict({"a": 1, "b": 2})
        c2 = Config.from_dict({"b": 3, "c": 4})
        merged = Config.merge(c1, c2)
        assert merged["a"] == 1
        assert merged["b"] == 3
        assert merged["c"] == 4

    def test_merge_preserves_sources(self) -> None:
        c1 = Config.from_dict({"a": 1})
        c2 = Config.from_dict({"b": 2})
        merged = Config.merge(c1, c2)
        assert len(merged.sources) == 2

    def test_merge_with_strategy(self) -> None:
        c1 = Config.from_dict({"hosts": ["a"]})
        c2 = Config.from_dict({"hosts": ["b"]})
        merged = Config.merge(c1, c2, merge_strategy=MergeStrategy.ADDITIVE)
        assert merged["hosts"] == ["a", "b"]


# ── Dict-like access ──────────────────────────────────────────────────────


class TestDictAccess:
    def test_getitem(self) -> None:
        cfg = Config.from_dict({"key": "value"})
        assert cfg["key"] == "value"

    def test_getitem_missing_raises_key_error(self) -> None:
        cfg = Config.from_dict({"key": "value"})
        with pytest.raises(KeyError):
            cfg["missing"]

    def test_get_with_default(self) -> None:
        cfg = Config.from_dict({"key": "value"})
        assert cfg.get("missing", "fallback") == "fallback"

    def test_get_existing(self) -> None:
        cfg = Config.from_dict({"key": "value"})
        assert cfg.get("key") == "value"

    def test_contains(self) -> None:
        cfg = Config.from_dict({"key": "value"})
        assert "key" in cfg
        assert "missing" not in cfg

    def test_len(self) -> None:
        cfg = Config.from_dict({"a": 1, "b": 2, "c": 3})
        assert len(cfg) == 3

    def test_iter(self) -> None:
        cfg = Config.from_dict({"a": 1, "b": 2})
        assert set(cfg) == {"a", "b"}

    def test_to_dict_returns_deep_copy(self) -> None:
        cfg = Config.from_dict({"nested": {"key": "value"}})
        d = cfg.to_dict()
        d["nested"]["key"] = "changed"
        assert cfg["nested"]["key"] == "value"  # original unchanged

    def test_data_property(self) -> None:
        cfg = Config.from_dict({"x": 1})
        assert cfg.data == {"x": 1}


# ── Dunder methods ─────────────────────────────────────────────────────────


class TestDunder:
    def test_repr(self) -> None:
        cfg = Config.from_dict({"app": {}, "db": {}})
        r = repr(cfg)
        assert "Config" in r
        assert "app" in r
        assert "db" in r

    def test_eq_same_data(self) -> None:
        c1 = Config.from_dict({"key": "value"})
        c2 = Config.from_dict({"key": "value"})
        assert c1 == c2

    def test_eq_different_data(self) -> None:
        c1 = Config.from_dict({"key": "a"})
        c2 = Config.from_dict({"key": "b"})
        assert c1 != c2

    def test_eq_not_implemented_for_other_types(self) -> None:
        cfg = Config.from_dict({"key": "value"})
        assert cfg != "not a config"
        assert cfg != 42


# ── Merge strategies on file loaders ───────────────────────────────────────


class TestFileLoaderMergeStrategies:
    def test_additive_toml(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.toml"
        f2 = tmp_path / "b.toml"
        f1.write_text('[s]\nhosts = ["a"]\n', encoding="utf-8")
        f2.write_text('[s]\nhosts = ["b"]\n', encoding="utf-8")
        cfg = Config.from_toml(
            f1,
            f2,
            key_strategies={"s.hosts": MergeStrategy.ADDITIVE},
        )
        assert cfg["s"]["hosts"] == ["a", "b"]

    def test_typesafe_toml_raises_on_mismatch(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.toml"
        f2 = tmp_path / "b.toml"
        f1.write_text("port = 8000\n", encoding="utf-8")
        f2.write_text('port = "not-a-number"\n', encoding="utf-8")
        with pytest.raises(TypeError):
            Config.from_toml(f1, f2, merge_strategy=MergeStrategy.TYPESAFE)
