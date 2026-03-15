"""Tests for from_dir() secret descriptor autodetection and remote loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from imbrex import Config
from imbrex._exceptions import ConfigSecretDescriptorError


def test_from_dir_merges_remote_secrets_last(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "defaults.toml").write_text(
        '[database]\npassword = "from-file"\n',
        encoding="utf-8",
    )

    (config_dir / "secrets.toml").write_text(
        """
[aws]
enabled = true
region_name = "eu-central-1"
[[aws.items]]
path = "database.password"
secret_id = "app/db/password"
        """.strip(),
        encoding="utf-8",
    )

    import imbrex._secrets as _secrets

    def fake_aws(_: _secrets.ProviderConfig) -> dict[str, object]:
        return {"database": {"password": "from-remote"}}

    monkeypatch.setitem(_secrets._PROVIDER_FETCHERS, "aws", fake_aws)

    cfg = Config.from_dir(config_dir, extension="toml")

    assert cfg.get("database.password") == "from-remote"
    assert any(src.startswith("<secret:aws>") for src in cfg.sources)


def test_from_dir_detects_dot_secrets_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "defaults.toml").write_text(
        '[app]\nname = "base"\n', encoding="utf-8"
    )
    (config_dir / ".secrets.yaml").write_text(
        """
aws:
  enabled: true
  region_name: eu-central-1
  items:
    - path: app.name
      secret_id: app/name
        """.strip(),
        encoding="utf-8",
    )

    import imbrex._secrets as _secrets

    def fake_aws(_: _secrets.ProviderConfig) -> dict[str, object]:
        return {"app": {"name": "secret-name"}}

    monkeypatch.setitem(_secrets._PROVIDER_FETCHERS, "aws", fake_aws)

    cfg = Config.from_dir(config_dir, extension="toml")

    assert cfg.get("app.name") == "secret-name"


def test_descriptor_validation_happens_before_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "defaults.toml").write_text('[x]\nvalue = "base"\n', encoding="utf-8")

    # region_name is required for aws and should fail validation.
    (config_dir / "secrets.toml").write_text(
        """
[aws]
enabled = true
[[aws.items]]
path = "x.value"
secret_id = "x/value"
        """.strip(),
        encoding="utf-8",
    )

    import imbrex._secrets as _secrets

    calls = {"aws": 0}

    def fake_aws(_: _secrets.ProviderConfig) -> dict[str, object]:
        calls["aws"] += 1
        return {"x": {"value": "secret"}}

    monkeypatch.setitem(_secrets._PROVIDER_FETCHERS, "aws", fake_aws)

    with pytest.raises(ConfigSecretDescriptorError):
        Config.from_dir(config_dir, extension="toml")

    assert calls["aws"] == 0


def test_descriptor_env_overrides_apply_before_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "defaults.toml").write_text('[x]\nvalue = "base"\n', encoding="utf-8")

    # Missing aws.region_name in file, but provided through env override.
    (config_dir / "secrets.toml").write_text(
        """
[aws]
enabled = true
[[aws.items]]
path = "x.value"
secret_id = "x/value"
        """.strip(),
        encoding="utf-8",
    )

    import imbrex._secrets as _secrets

    def fake_aws(cfg: _secrets.ProviderConfig) -> dict[str, object]:
        assert getattr(cfg, "region_name", None) == "eu-west-1"
        return {"x": {"value": "from-secret"}}

    monkeypatch.setitem(_secrets._PROVIDER_FETCHERS, "aws", fake_aws)
    monkeypatch.setenv("IMBREX_SECRETS__AWS__REGION_NAME", "eu-west-1")

    cfg = Config.from_dir(config_dir, extension="toml")
    assert cfg.get("x.value") == "from-secret"
