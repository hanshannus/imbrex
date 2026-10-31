# Remote Secrets in `from_dir()`

Use `Config.from_dir()` as the single entrypoint for local config files and
remote secret providers (AWS, Azure, GCP).

## Directory layout

```text
config/
├── defaults.toml
├── development.toml
├── production.toml
├── local.toml
├── secrets.toml      # secret descriptor
└── .secrets.yaml     # optional additional descriptor
```

Descriptor files are auto-detected by filename stem:

- `secrets.*`
- `secret.*`
- `.secrets.*`
- `.secret.*`

## Load flow

`from_dir()` now performs this sequence:

1. Scan directory and split into regular config files vs secret descriptors.
2. Parse and validate each descriptor (fail fast on schema errors).
3. Apply env-var overrides from `IMBREX_SECRETS__*`.
4. Fetch all enabled providers concurrently.
5. Merge fetched secrets on top of file-based config.
6. Return one merged `Config` object.

## Descriptor schema

Each provider has an `items` list. Every item maps one remote secret to one
final config path.

- `path`: target config path (dot notation)
- `secret_id`: provider-native secret name/id
- `version` (optional): provider-specific version/stage
- `field` (optional): extract a key from JSON payloads

### AWS (`secrets.toml`)

```toml
[aws]
enabled = true
region_name = "eu-central-1"
# profile_name = "my-profile"  # optional

[[aws.items]]
path = "database.password"
secret_id = "myapp/prod/database"
field = "password"
```

### Azure (`secrets.toml`)

```toml
[azure]
enabled = true
vault_url = "https://my-vault.vault.azure.net/"

[[azure.items]]
path = "database.password"
secret_id = "db-password"
```

### GCP (`secrets.toml`)

```toml
[gcp]
enabled = true
project_id = "my-gcp-project"

[[gcp.items]]
path = "database.password"
secret_id = "db-password"
version = "latest"
```

## Environment overrides for descriptors

Descriptor values can be overridden without editing files:

```bash
export IMBREX_SECRETS__AWS__REGION_NAME="eu-west-1"
export IMBREX_SECRETS__AZURE__VAULT_URL="https://prod-vault.vault.azure.net/"
export IMBREX_SECRETS__GCP__PROJECT_ID="prod-project"
```

## Usage

```python
from imbrex import Config

cfg = Config.from_dir("config/", extension="toml", env="production")

# Standard config + remote secrets are available in one merged object
print(cfg.get("database.password"))
print(cfg.sources)  # includes entries like <secret:aws>
```

## Caching and refreshing

By default every `from_dir()` / `load_config()` call fetches secrets again.
That is the safe choice, but slow and rate-limited if you load config often.
Opt in to a cache with `secrets_ttl` (seconds):

```python
cfg = imbrex.load_config("config/", secrets_ttl=300)   # fetched
cfg = imbrex.load_config("config/", secrets_ttl=300)   # served from cache
```

- The cache is per provider and keyed on the descriptor (region, vault,
  project, items, profile), so changing the descriptor fetches fresh values.
- Entries expire after `secrets_ttl` seconds. `None` or `0` turns caching off.
- Failed fetches are never cached.
- The cache lives in process memory only. `imbrex.clear_secrets_cache()`
  empties it.

### `reload()`

Secrets rotate and files change. `reload()` rebuilds a config from the same
inputs, re-reading files, `.env` and environment variables and fetching
secrets fresh:

```python
cfg = imbrex.load_config("config/", env_prefix="APP_", secrets_ttl=300)

# later: on SIGHUP, on a timer, from an admin endpoint ...
cfg = cfg.reload()
```

- It returns a **new** `Config` and mutates nothing, so swap your reference
  atomically. Readers holding the old object keep a consistent snapshot.
- If anything fails (a provider is down, a file no longer parses) the
  exception propagates and the old config stays valid, so a bad reload never
  leaves you with half a config.
- `reload(refresh_secrets=False)` lets the `secrets_ttl` cache answer instead
  of fetching.
- Only results of `Config.from_dir()` and `imbrex.load_config()` can reload.
  Others (`from_dict`, `merge`, `interpolate`, `with_overrides`, ...) raise
  `ImbrexError`, because they do not know how to rebuild themselves.

```python
import signal

def on_sighup(*_):
    global cfg
    try:
        cfg = cfg.reload()
    except imbrex.ImbrexError as exc:
        log.warning("config reload failed, keeping the old config: %s", exc)

signal.signal(signal.SIGHUP, on_sighup)
```

## Install provider dependencies

```bash
pip install "imbrex[aws]"
pip install "imbrex[azure]"
pip install "imbrex[gcp]"
# or all remote providers
pip install "imbrex[secrets]"
```

## Errors

- Invalid descriptor schema raises `ConfigSecretDescriptorError`.
- Provider fetch failures raise `SecretProviderError`.
