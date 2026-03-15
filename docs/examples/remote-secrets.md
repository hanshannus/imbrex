# Example: `from_dir()` with Remote Secrets

This example keeps local defaults in files and fetches sensitive values from
remote secret providers, all through `Config.from_dir()`.

## Example layout

```text
config/
├── defaults.toml
├── production.toml
└── secrets.toml
```

`config/defaults.toml`:

```toml
[app]
name = "MyApp"
debug = false

[database]
host = "prod-db"
port = 5432
user = "app"
password = "placeholder"
```

`config/production.toml`:

```toml
[app]
debug = false

[database]
name = "myapp"
```

`config/secrets.toml`:

```toml
[aws]
enabled = true
region_name = "eu-central-1"

[[aws.items]]
path = "database.password"
secret_id = "myapp/prod/database"
field = "password"
```

## Load in one call

```python
from imbrex import Config

cfg = Config.from_dir("config/", extension="toml", env="production")

print(cfg.get("database.host"))
print(cfg.get("database.password"))
print(cfg.sources)
```

Expected behavior:

- `defaults.toml` + `production.toml` merge by priority.
- `secrets.toml` is treated as a descriptor, not normal file config.
- Fetched secret value is merged last and wins over file placeholders.
- `cfg.sources` includes provider source tags (`<secret:aws>`, etc.).

## Local override of descriptor values

```bash
export IMBREX_SECRETS__AWS__REGION_NAME="eu-west-1"
```

That lets one `secrets.toml` work across environments without edits.
