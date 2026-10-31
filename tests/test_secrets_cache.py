"""Secret caching (TTL) and ``Config.reload()``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import imbrex
import imbrex._secrets as _secrets
import imbrex._secrets_cache as _cache
from imbrex import Config, ImbrexError, SecretProviderError


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    c = Clock()
    monkeypatch.setattr(_cache, "monotonic", c)
    imbrex.clear_secrets_cache()
    yield c  # type: ignore[misc]
    imbrex.clear_secrets_cache()


class Remote:
    """Controllable fake AWS fetcher that counts calls."""

    def __init__(self) -> None:
        self.calls = 0
        self.value = "v1"
        self.fail = False

    def __call__(self, cfg: Any) -> dict[str, Any]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return {"database": {"password": self.value, "region": cfg.region_name}}


@pytest.fixture
def remote(monkeypatch: pytest.MonkeyPatch) -> Remote:
    r = Remote()
    monkeypatch.setitem(_secrets._PROVIDER_FETCHERS, "aws", r)
    return r


@pytest.fixture
def cfg_dir(tmp_path: Path) -> Path:
    d = tmp_path / "config"
    d.mkdir()
    (d / "defaults.toml").write_text('[app]\nname = "one"\n')
    (d / "secrets.toml").write_text(
        '[aws]\nregion_name = "eu-central-1"\n'
        '[[aws.items]]\npath = "database.password"\nsecret_id = "x"\n'
    )
    return d


class TestCache:
    def test_no_ttl_fetches_every_time(self, cfg_dir: Path, remote: Remote) -> None:
        Config.from_dir(cfg_dir)
        Config.from_dir(cfg_dir)
        assert remote.calls == 2

    def test_ttl_serves_second_load_from_cache(
        self, cfg_dir: Path, remote: Remote
    ) -> None:
        a = Config.from_dir(cfg_dir, secrets_ttl=60)
        remote.value = "v2"  # would be visible if it refetched
        b = Config.from_dir(cfg_dir, secrets_ttl=60)
        assert remote.calls == 1
        assert a["database.password"] == b["database.password"] == "v1"

    def test_expires_after_ttl(
        self, cfg_dir: Path, remote: Remote, clock: Clock
    ) -> None:
        Config.from_dir(cfg_dir, secrets_ttl=60)
        clock.now += 59
        Config.from_dir(cfg_dir, secrets_ttl=60)
        assert remote.calls == 1
        clock.now += 2
        remote.value = "v2"
        cfg = Config.from_dir(cfg_dir, secrets_ttl=60)
        assert remote.calls == 2 and cfg["database.password"] == "v2"

    def test_clear_secrets_cache(self, cfg_dir: Path, remote: Remote) -> None:
        Config.from_dir(cfg_dir, secrets_ttl=60)
        imbrex.clear_secrets_cache()
        Config.from_dir(cfg_dir, secrets_ttl=60)
        assert remote.calls == 2

    def test_cache_is_isolated_from_callers(
        self, cfg_dir: Path, remote: Remote
    ) -> None:
        a = Config.from_dir(cfg_dir, secrets_ttl=60)
        a.data["database"]["password"] = "tampered"
        b = Config.from_dir(cfg_dir, secrets_ttl=60)
        assert b["database.password"] == "v1"

    def test_different_descriptors_do_not_share_entries(
        self, cfg_dir: Path, remote: Remote
    ) -> None:
        Config.from_dir(cfg_dir, secrets_ttl=60)
        (cfg_dir / "secrets.toml").write_text(
            '[aws]\nregion_name = "us-east-1"\n'
            '[[aws.items]]\npath = "database.password"\nsecret_id = "x"\n'
        )
        cfg = Config.from_dir(cfg_dir, secrets_ttl=60)
        assert remote.calls == 2 and cfg["database.region"] == "us-east-1"

    def test_failures_are_not_cached(self, cfg_dir: Path, remote: Remote) -> None:
        remote.fail = True
        with pytest.raises(SecretProviderError):
            Config.from_dir(cfg_dir, secrets_ttl=60)
        remote.fail = False
        assert Config.from_dir(cfg_dir, secrets_ttl=60)["database.password"] == "v1"

    def test_zero_ttl_disables_caching(self, cfg_dir: Path, remote: Remote) -> None:
        Config.from_dir(cfg_dir, secrets_ttl=0)
        Config.from_dir(cfg_dir, secrets_ttl=0)
        assert remote.calls == 2


class TestReload:
    def test_picks_up_changed_file_and_secret(
        self, cfg_dir: Path, remote: Remote
    ) -> None:
        cfg = Config.from_dir(cfg_dir, secrets_ttl=60)
        (cfg_dir / "defaults.toml").write_text('[app]\nname = "two"\n')
        remote.value = "v2"
        new = cfg.reload()
        assert new["app.name"] == "two" and new["database.password"] == "v2"
        assert cfg["app.name"] == "one" and cfg["database.password"] == "v1"
        assert new is not cfg

    def test_reload_refreshes_secrets_by_default(
        self, cfg_dir: Path, remote: Remote
    ) -> None:
        cfg = Config.from_dir(cfg_dir, secrets_ttl=3600)
        remote.value = "v2"
        assert cfg.reload()["database.password"] == "v2"

    def test_reload_can_use_the_cache(self, cfg_dir: Path, remote: Remote) -> None:
        cfg = Config.from_dir(cfg_dir, secrets_ttl=3600)
        remote.value = "v2"
        assert cfg.reload(refresh_secrets=False)["database.password"] == "v1"
        assert remote.calls == 1

    def test_reloaded_config_can_reload_again(
        self, cfg_dir: Path, remote: Remote
    ) -> None:
        cfg = Config.from_dir(cfg_dir).reload()
        remote.value = "v3"
        assert cfg.reload()["database.password"] == "v3"

    def test_keeps_frozen(self, cfg_dir: Path, remote: Remote) -> None:
        assert Config.from_dir(cfg_dir, freeze=True).reload().is_frozen

    def test_works_without_secrets(self, tmp_path: Path) -> None:
        (tmp_path / "defaults.toml").write_text("a = 1\n")
        cfg = Config.from_dir(tmp_path)
        (tmp_path / "defaults.toml").write_text("a = 2\n")
        assert cfg.reload()["a"] == 2

    def test_failed_reload_raises_and_keeps_old(
        self, cfg_dir: Path, remote: Remote
    ) -> None:
        cfg = Config.from_dir(cfg_dir)
        remote.fail = True
        with pytest.raises(SecretProviderError):
            cfg.reload()
        assert cfg["database.password"] == "v1"

    @pytest.mark.parametrize(
        "build",
        [
            lambda: Config.from_dict({"a": 1}),
            lambda: Config.from_dict({"a": "${env:X:-1}"}).interpolate(),
            lambda: Config.from_dict({"a": 1}).with_overrides({"a": 2}),
        ],
    )
    def test_other_configs_cannot_reload(self, build: Any) -> None:
        with pytest.raises(ImbrexError, match="reload"):
            build().reload()


class TestLoadConfigReload:
    def test_reload_rereads_env_and_files(
        self, cfg_dir: Path, remote: Remote, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_LEVEL", "info")
        cfg = imbrex.load_config(cfg_dir, env_prefix="APP_", dotenv=None)
        monkeypatch.setenv("APP_LEVEL", "debug")
        remote.value = "v2"
        new = cfg.reload()
        assert new["level"] == "debug" and new["database.password"] == "v2"
        assert cfg["level"] == "info"

    def test_secrets_ttl_passes_through(self, cfg_dir: Path, remote: Remote) -> None:
        imbrex.load_config(cfg_dir, dotenv=None, secrets_ttl=60)
        imbrex.load_config(cfg_dir, dotenv=None, secrets_ttl=60)
        assert remote.calls == 1

    def test_reload_keeps_interpolation_and_ttl_settings(
        self, cfg_dir: Path, remote: Remote, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (cfg_dir / "defaults.toml").write_text('[app]\nname = "${env:WHO:-x}"\n')
        monkeypatch.setenv("WHO", "a")
        cfg = imbrex.load_config(cfg_dir, dotenv=None, secrets_ttl=60)
        monkeypatch.setenv("WHO", "b")
        assert cfg.reload()["app.name"] == "b"

    def test_overrides_survive_reload(self, cfg_dir: Path, remote: Remote) -> None:
        cfg = imbrex.load_config(cfg_dir, dotenv=None, overrides={"app": {"x": 1}})
        assert cfg.reload()["app.x"] == 1
