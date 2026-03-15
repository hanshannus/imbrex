"""Remote secret descriptor parsing and provider dispatch for Config.from_dir()."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from imbrex._exceptions import ConfigSecretDescriptorError, SecretProviderError
from imbrex._merge import MergeStrategy, deep_merge
from imbrex._parsers import parse_file

# Descriptor filename stems that should be treated as secret descriptors.
SECRET_DESCRIPTOR_STEMS: set[str] = {
    "secret",
    "secrets",
    ".secret",
    ".secrets",
}

# Fixed merge priority slot for fetched remote secrets.
REMOTE_SECRETS_PRIORITY: int = 800


class SecretItem(BaseModel):
    """One remote secret mapped into one config path."""

    model_config = ConfigDict(extra="forbid")

    path: str
    secret_id: str
    version: str | None = None
    field: str | None = None


class _ProviderBase(BaseModel):
    """Shared options for all providers."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    items: list[SecretItem] = Field(default_factory=list)


class AwsSecretsConfig(_ProviderBase):
    region_name: str
    profile_name: str | None = None


class AzureSecretsConfig(_ProviderBase):
    vault_url: str


class GcpSecretsConfig(_ProviderBase):
    project_id: str


class SecretsDescriptor(BaseModel):
    """Validated schema for one secrets descriptor file."""

    model_config = ConfigDict(extra="forbid")

    aws: AwsSecretsConfig | None = None
    azure: AzureSecretsConfig | None = None
    gcp: GcpSecretsConfig | None = None


ProviderConfig = AwsSecretsConfig | AzureSecretsConfig | GcpSecretsConfig
ProviderFetcher = Callable[[Any], dict[str, Any]]


def is_secret_descriptor(path: Path) -> bool:
    """Return True when the filename stem marks this file as a secret descriptor."""
    return path.stem.lower() in SECRET_DESCRIPTOR_STEMS


def apply_descriptor_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    """Overlay IMBREX_SECRETS__* env vars onto a descriptor-like dict."""
    from imbrex._config import Config

    env_overlay = Config.from_env(prefix="IMBREX_SECRETS__", separator="__").to_dict()
    if not env_overlay:
        return raw
    return deep_merge(raw, env_overlay, strategy=MergeStrategy.REPLACE)


def _coerce_secret_value(raw: str, *, field: str | None) -> Any:
    """Attempt JSON decode first so structured secrets can be merged naturally."""
    value: Any = raw
    try:
        parsed = json.loads(raw)
        value = parsed
    except json.JSONDecodeError:
        value = raw

    if field is None:
        return value

    if not isinstance(value, dict) or field not in value:
        raise KeyError(f"field {field!r} not found in secret payload")
    return value[field]


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    node: dict[str, Any] = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def _fetch_aws(config: AwsSecretsConfig) -> dict[str, Any]:
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - depends on optional deps
        raise RuntimeError(
            "AWS support requires boto3. Install with: pip install imbrex[aws]"
        ) from exc

    if config.profile_name:
        session = boto3.session.Session(profile_name=config.profile_name)
        client = session.client("secretsmanager", region_name=config.region_name)
    else:
        client = boto3.client("secretsmanager", region_name=config.region_name)

    out: dict[str, Any] = {}
    for item in config.items:
        kwargs: dict[str, Any] = {"SecretId": item.secret_id}
        if item.version:
            kwargs["VersionStage"] = item.version

        response = client.get_secret_value(**kwargs)
        secret_str = response.get("SecretString")
        if secret_str is None and response.get("SecretBinary") is not None:
            secret_str = response["SecretBinary"].decode()
        if secret_str is None:
            raise RuntimeError(f"AWS secret {item.secret_id!r} returned no payload")

        _set_path(out, item.path, _coerce_secret_value(secret_str, field=item.field))

    return out


def _fetch_azure(config: AzureSecretsConfig) -> dict[str, Any]:
    try:
        from azure.identity import (
            DefaultAzureCredential,
        )
        from azure.keyvault.secrets import (
            SecretClient,
        )
    except ImportError as exc:  # pragma: no cover - depends on optional deps
        raise RuntimeError(
            "Azure support requires azure-identity and azure-keyvault-secrets. "
            "Install with: pip install imbrex[azure]"
        ) from exc

    client = SecretClient(
        vault_url=config.vault_url,
        credential=DefaultAzureCredential(),
    )

    out: dict[str, Any] = {}
    for item in config.items:
        secret = client.get_secret(name=item.secret_id, version=item.version)
        _set_path(out, item.path, _coerce_secret_value(secret.value, field=item.field))

    return out


def _fetch_gcp(config: GcpSecretsConfig) -> dict[str, Any]:
    try:
        import google.cloud.secretmanager as secretmanager
    except ImportError as exc:  # pragma: no cover - depends on optional deps
        raise RuntimeError(
            "GCP support requires google-cloud-secret-manager. "
            "Install with: pip install imbrex[gcp]"
        ) from exc

    client = secretmanager.SecretManagerServiceClient()

    out: dict[str, Any] = {}
    for item in config.items:
        version = item.version or "latest"
        secret_path = (
            f"projects/{config.project_id}/secrets/{item.secret_id}/versions/{version}"
        )
        response = client.access_secret_version(request={"name": secret_path})
        payload = response.payload.data.decode("utf-8")
        _set_path(out, item.path, _coerce_secret_value(payload, field=item.field))

    return out


_PROVIDER_FETCHERS: dict[str, ProviderFetcher] = {
    "aws": _fetch_aws,
    "azure": _fetch_azure,
    "gcp": _fetch_gcp,
}


def _run_async(coro: Any) -> Any:
    """Run async code from both sync and already-running-loop contexts."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}
    errors: list[Exception] = []

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:  # pragma: no cover - unlikely in tests
            errors.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if errors:
        raise errors[0]
    return result.get("value")


def _fetch_provider(
    provider_name: str,
    provider_config: ProviderConfig,
    *,
    provider_fetchers: dict[str, ProviderFetcher],
) -> tuple[dict[str, Any], str]:
    fetcher = provider_fetchers[provider_name]
    try:
        return fetcher(provider_config), provider_name
    except Exception as exc:
        raise SecretProviderError(provider_name, exc) from exc


async def _fetch_all(
    plans: list[tuple[str, ProviderConfig]],
    *,
    provider_fetchers: dict[str, ProviderFetcher],
) -> list[tuple[dict[str, Any], str]]:
    tasks = [
        asyncio.to_thread(
            _fetch_provider,
            provider_name,
            provider_config,
            provider_fetchers=provider_fetchers,
        )
        for provider_name, provider_config in plans
    ]
    result = await asyncio.gather(*tasks)
    return list(result)


def load_remote_secrets(
    descriptor_paths: list[Path],
    *,
    provider_fetchers: dict[str, ProviderFetcher] | None = None,
    merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
    key_strategies: dict[str, MergeStrategy] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Load and fetch secrets from descriptor files and return merged data + sources."""
    if not descriptor_paths:
        return {}, []

    fetchers = provider_fetchers or _PROVIDER_FETCHERS
    plans: list[tuple[str, ProviderConfig]] = []

    for path in descriptor_paths:
        raw = parse_file(path)
        raw = apply_descriptor_env_overrides(raw)

        try:
            descriptor = SecretsDescriptor.model_validate(raw)
        except ValidationError as exc:
            raise ConfigSecretDescriptorError(path, exc) from exc

        for provider_name in ("aws", "azure", "gcp"):
            provider_cfg = getattr(descriptor, provider_name)
            if provider_cfg and provider_cfg.enabled:
                plans.append((provider_name, provider_cfg))

    if not plans:
        return {}, []

    fetched = _run_async(_fetch_all(plans, provider_fetchers=fetchers))

    dicts: list[dict[str, Any]] = []
    sources: list[str] = []
    for data, provider in fetched:
        dicts.append(data)
        sources.append(f"<secret:{provider}>")

    merged = deep_merge(
        *dicts,
        strategy=merge_strategy,
        key_strategies=key_strategies,
    )
    return merged, sources
