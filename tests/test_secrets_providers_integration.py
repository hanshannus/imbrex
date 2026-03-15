"""
Opt-in integration tests for AWS/Azure/GCP secret providers.

These tests are intentionally skipped by default because they require
real cloud credentials and test secret resources.

Enable with:
    IMBREX_RUN_SECRET_INTEGRATION=1
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from imbrex import Config

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("IMBREX_RUN_SECRET_INTEGRATION") != "1",
        reason="set IMBREX_RUN_SECRET_INTEGRATION=1 to run cloud integration tests",
    ),
]


def _require_env(*names: str) -> dict[str, str]:
    values: dict[str, str] = {}
    missing: list[str] = []
    for name in names:
        val = os.getenv(name)
        if not val:
            missing.append(name)
        else:
            values[name] = val
    if missing:
        pytest.skip(f"missing required environment variables: {', '.join(missing)}")
    return values


@pytest.mark.aws
def test_aws_secrets_manager_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("boto3")

    env = _require_env("AWS_REGION", "AWS_TEST_SECRET_ID")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "defaults.toml").write_text(
        '[app]\nname = "base"\n', encoding="utf-8"
    )
    (config_dir / "secrets.toml").write_text(
        f"""
[aws]
enabled = true
region_name = "{env["AWS_REGION"]}"
[[aws.items]]
path = "integration.aws.payload"
secret_id = "{env["AWS_TEST_SECRET_ID"]}"
        """.strip(),
        encoding="utf-8",
    )

    cfg = Config.from_dir(config_dir, extension="toml")
    value = cfg.get("integration.aws.payload")

    assert value is not None
    assert any(src.startswith("<secret:aws>") for src in cfg.sources)


@pytest.mark.azure
def test_azure_key_vault_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("azure.identity")
    pytest.importorskip("azure.keyvault.secrets")

    env = _require_env("AZURE_KEYVAULT_URL", "AZURE_TEST_SECRET_NAME")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "defaults.toml").write_text(
        '[app]\nname = "base"\n', encoding="utf-8"
    )
    (config_dir / "secrets.toml").write_text(
        f"""
[azure]
enabled = true
vault_url = "{env["AZURE_KEYVAULT_URL"]}"
[[azure.items]]
path = "integration.azure.payload"
secret_id = "{env["AZURE_TEST_SECRET_NAME"]}"
        """.strip(),
        encoding="utf-8",
    )

    cfg = Config.from_dir(config_dir, extension="toml")
    value = cfg.get("integration.azure.payload")

    assert value is not None
    assert any(src.startswith("<secret:azure>") for src in cfg.sources)


@pytest.mark.gcp
def test_gcp_secret_manager_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("google.cloud.secretmanager")

    env = _require_env("GCP_PROJECT_ID", "GCP_TEST_SECRET_ID")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "defaults.toml").write_text(
        '[app]\nname = "base"\n', encoding="utf-8"
    )
    (config_dir / "secrets.toml").write_text(
        f"""
[gcp]
enabled = true
project_id = "{env["GCP_PROJECT_ID"]}"
[[gcp.items]]
path = "integration.gcp.payload"
secret_id = "{env["GCP_TEST_SECRET_ID"]}"
        """.strip(),
        encoding="utf-8",
    )

    cfg = Config.from_dir(config_dir, extension="toml")
    value = cfg.get("integration.gcp.payload")

    assert value is not None
    assert any(src.startswith("<secret:gcp>") for src in cfg.sources)
