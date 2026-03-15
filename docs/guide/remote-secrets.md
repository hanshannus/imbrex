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

