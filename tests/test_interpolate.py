"""``${...}`` interpolation."""

from __future__ import annotations

from pathlib import Path

import pytest

import imbrex
from imbrex import Config, ConfigInterpolationError


def interp(data: dict, env: dict | None = None) -> dict:  # type: ignore[type-arg]
    return Config.from_dict(data).interpolate(env=env or {}).to_dict()


class TestReferences:
    def test_key_reference_inside_string(self) -> None:
        out = interp({"db": {"host": "h", "url": "pg://${db.host}/app"}})
        assert out["db"]["url"] == "pg://h/app"

    def test_whole_value_keeps_type(self) -> None:
        out = interp({"server": {"port": 8080}, "public": "${server.port}"})
        assert out["public"] == 8080

    def test_embedded_non_string_is_stringified(self) -> None:
        out = interp({"port": 80, "addr": "host:${port}"})
        assert out["addr"] == "host:80"

    def test_whole_value_can_reference_a_section(self) -> None:
        out = interp({"a": {"x": 1}, "b": "${a}"})
        assert out["b"] == {"x": 1}

    def test_chained_references(self) -> None:
        out = interp({"a": "1", "b": "${a}2", "c": "${b}3"})
        assert out["c"] == "123"

    def test_inside_lists(self) -> None:
        out = interp({"h": "x", "hosts": ["${h}.a", "${h}.b"]})
        assert out["hosts"] == ["x.a", "x.b"]

    def test_non_strings_untouched(self) -> None:
        assert interp({"a": 1, "b": True, "c": None}) == {"a": 1, "b": True, "c": None}

    def test_input_not_mutated(self) -> None:
        cfg = Config.from_dict({"a": "x", "b": "${a}"})
        cfg.interpolate()
        assert cfg["b"] == "${a}"


class TestEnv:
    def test_env_reference(self) -> None:
        assert interp({"u": "${env:HOME_X}/app"}, {"HOME_X": "/h"})["u"] == "/h/app"

    def test_reads_os_environ_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IMBREX_T", "v")
        out = Config.from_dict({"a": "${env:IMBREX_T}"}).interpolate().to_dict()
        assert out["a"] == "v"

    def test_env_values_stay_strings(self) -> None:
        assert interp({"p": "${env:PORT}"}, {"PORT": "80"})["p"] == "80"


class TestDefaults:
    def test_env_default(self) -> None:
        assert interp({"a": "${env:NOPE:-fallback}"})["a"] == "fallback"

    def test_key_default(self) -> None:
        assert interp({"a": "${missing.key:-d}"})["a"] == "d"

    def test_empty_default(self) -> None:
        assert interp({"a": "x${env:NOPE:-}y"})["a"] == "xy"

    def test_default_unused_when_present(self) -> None:
        assert interp({"a": "${env:K:-d}"}, {"K": "real"})["a"] == "real"


class TestEscape:
    def test_double_dollar_is_literal(self) -> None:
        assert interp({"a": "cost $${5}"})["a"] == "cost ${5}"

    def test_lone_dollar_untouched(self) -> None:
        assert interp({"a": "$5 and ${"})["a"] == "$5 and ${"


class TestErrors:
    def test_missing_key(self) -> None:
        with pytest.raises(ConfigInterpolationError) as exc:
            interp({"a": "${nope}"})
        msg = str(exc.value)
        assert "${nope}" in msg and "'a'" in msg

    def test_missing_env(self) -> None:
        with pytest.raises(ConfigInterpolationError, match="MISSING_VAR"):
            interp({"a": "${env:MISSING_VAR}"})

    def test_cycle(self) -> None:
        with pytest.raises(ConfigInterpolationError, match="circular"):
            interp({"a": "${b}", "b": "${a}"})

    def test_self_reference(self) -> None:
        with pytest.raises(ConfigInterpolationError, match="circular"):
            interp({"a": "x${a}"})

    def test_is_imbrex_error(self) -> None:
        assert issubclass(ConfigInterpolationError, imbrex.ImbrexError)

    def test_error_names_nested_location(self) -> None:
        with pytest.raises(ConfigInterpolationError, match=r"hosts\.1"):
            interp({"hosts": ["ok", "${nope}"]})


class TestConfigIntegration:
    def test_frozen_state_preserved(self) -> None:
        cfg = Config.from_dict({"a": "x", "b": "${a}"}, freeze=True)
        out = cfg.interpolate()
        assert out.is_frozen and out["b"] == "x"

    def test_sources_preserved(self) -> None:
        cfg = Config.from_dict({"a": "x", "b": "${a}"})
        assert cfg.interpolate().sources == cfg.sources

    def test_explain_shows_resolved_values(self, tmp_path: Path) -> None:
        (tmp_path / "defaults.toml").write_text(
            '[db]\nhost = "h"\nurl = "pg://${db.host}"\n'
        )
        (tmp_path / "production.toml").write_text('[db]\nhost = "prod"\n')
        cfg = Config.from_dir(tmp_path, env="production").interpolate()
        ex = cfg.explain("db.url")
        assert ex.value == "pg://prod"
        assert ex.source.endswith("defaults.toml")

    def test_secret_values_stay_masked_in_explain(self) -> None:
        cfg = Config.from_dict({"pw": "x", "db": {"password": "${pw}"}}).interpolate()
        assert cfg.explain("db.password").value == "***"


class TestLoad:
    def test_load_config_interpolates_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "defaults.toml").write_text('url = "pg://${env:DBH}/x"\n')
        monkeypatch.setenv("DBH", "host1")
        assert imbrex.load_config(tmp_path, dotenv=None)["url"] == "pg://host1/x"

    def test_can_be_disabled(self, tmp_path: Path) -> None:
        (tmp_path / "defaults.toml").write_text('url = "${env:NOPE}"\n')
        cfg = imbrex.load_config(tmp_path, dotenv=None, interpolate=False)
        assert cfg["url"] == "${env:NOPE}"

    def test_references_across_sources(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "defaults.toml").write_text('url = "pg://${host}/x"\n')
        monkeypatch.setenv("APP_HOST", "fromenv")
        cfg = imbrex.load_config(tmp_path, env_prefix="APP_", dotenv=None)
        assert cfg["url"] == "pg://fromenv/x"


class TestLenientLayers:
    def test_overridden_layer_may_reference_missing_env(self) -> None:
        low = {"password": "${env:NOT_SET_ANYWHERE}"}
        high = {"password": "literal"}
        cfg = Config.from_dict(low, high).interpolate(env={})
        assert cfg["password"] == "literal"
        ex = cfg.explain("password")
        assert ex.value == "***" and len(ex.overridden) == 1

    def test_explain_overridden_value_is_raw_when_unresolvable(self) -> None:
        cfg = Config.from_dict({"u": "${env:NOPE}"}, {"u": "x"}).interpolate(env={})
        assert cfg.explain("u").overridden == [("<dict:0>", "${env:NOPE}")]
