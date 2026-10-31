# imbrex

**Hierarchical configuration management for Python.**

Load YAML, TOML, and JSON — individually or from a directory — merge them in
the correct priority order (`defaults → dev → staging → production → local`),
and validate the result with Pydantic v2.

```
uv add imbrex
uv add imbrex[pydantic]   # include Pydantic v2
uv add imbrex[secrets]    # include AWS/Azure/GCP providers
```

---

## Quick start

```python
import imbrex
from pydantic import BaseModel

class Database(BaseModel):
    url: str
    pool_size: int = 5

class Settings(BaseModel):
    debug: bool = False
    database: Database

settings = imbrex.load(Settings, "config/", env="production", env_prefix="APP_")
print(settings.database.url)
```

`load()` reads, lowest to highest priority: the files in `config/` (by
environment tier) → `.env` → `APP_*` environment variables → `overrides={...}`.
Types are coerced (`APP_DEBUG=true` → `True`), and errors name the key
(`database.url: Field required`) without echoing secret values.

### Where did this value come from?

```python
cfg = imbrex.load_config("config/", env="production", env_prefix="APP_")
print(cfg.explain("database.url"))
# database.url = 'postgres://prod'
#   from config/production.toml
#   overrides config/defaults.toml: 'sqlite:///default.db'

cfg.database.url          # attribute access; cfg["database.url"] also works
cfg.to_dict(redact=True)  # safe to log
```

### Reference other values

```toml
[database]
host = "db.internal"
url  = "postgresql://${database.host}/app"
user = "${env:DB_USER:-app}"
```

### Command line

```bash
imbrex show --env production --prefix APP_   # merged config, secrets masked
imbrex explain database.url --env production # where did this value come from?
imbrex validate myapp.settings:Settings      # CI gate: exit 1 if invalid
imbrex diff config staging production        # what changes between environments
```

Need finer control? Everything `load()` does is available as building blocks
below: `Config.from_dir`, `from_dotenv`, `from_env`, `merge`, ...

---

## Loading methods

### Single and multiple files

Files are merged **left-to-right** — the *last* file wins.

```python
cfg = Config.from_toml("settings.toml")
cfg = Config.from_yaml("settings.yaml")
cfg = Config.from_json("settings.json")
cfg = Config.from_file("settings.toml")          # auto-detect from extension

cfg = Config.from_toml("defaults.toml", "production.toml")
cfg = Config.from_file("defaults.toml", "overrides.yaml", "secrets.json")
```

### Directory — automatic hierarchical ordering

```python
cfg = Config.from_dir("config/", extension="toml", env="production")
cfg = Config.from_dir("config/", extension="yaml", recursive=True)
```

`from_dir()` can also auto-detect secret descriptor files (`secrets.*`,
`.secrets.*`), fetch remote values from AWS/Azure/GCP, and merge them into
the same final config object.

Default priority tiers (loaded low → high, later files win):

| Stem(s)                      | Priority |
|------------------------------|----------|
| `defaults`, `default`        | 100      |
| `base`, `common`, `shared`   | 200      |
| `development`, `dev`         | 300      |
| `test`, `testing`, `staging` | 400      |
| `production`, `prod`         | 500      |
| `local`                      | 600      |
| `secrets`, `secret`          | 700      |

When `env="development"`, files above that tier (`production.toml`) are
excluded automatically.

**Explicit order** (bypasses the priority table):

```python
cfg = Config.from_dir(
    "config/", extension="toml",
    order=["defaults", "development", "production"],
)
```

### Raw data

```python
cfg = Config.from_dict({"db": {"url": "sqlite:///default.db"}}, {"db": {"url": "postgres://..."}})
cfg = Config.from_string('[cache]\nbackend = "redis"', fmt="toml")
cfg = Config.from_env(prefix="APP_")    # APP_DATABASE__URL → database.url
cfg = Config.from_env(prefix="APP_", coerce=True)   # "true" → True, "8080" → 8080
cfg = Config.from_dotenv(".env", prefix="APP_")     # same rules, read from a file
```

### Merge Config objects

```python
merged = Config.merge(base_cfg, env_cfg, secret_cfg)
```

---

## Merge strategies

```python
from imbrex import MergeStrategy

cfg = Config.from_dir("config/", extension="toml", merge_strategy=MergeStrategy.ADDITIVE)

# Per-key override
cfg = Config.from_dir(
    "config/", extension="toml", env="production",
    key_strategies={"server.allowed_hosts": MergeStrategy.ADDITIVE},
)
```

| Strategy   | Behaviour                                     |
|------------|-----------------------------------------------|
| `REPLACE`  | Higher-priority values always win (default)   |
| `ADDITIVE` | Lists concatenated; scalars replaced          |
| `TYPESAFE` | Like REPLACE but raises on type mismatch      |

---

## Dict-like access

```python
cfg["app"]
cfg.get("missing", "default")
"app" in cfg
cfg.to_dict()      # deep copy as plain dict
cfg.sources        # ordered list of source paths/labels
```

---

## Documentation

Full documentation is available at
**[hanshannus.github.io/imbrex](https://hanshannus.github.io/imbrex)** — including:

- [Getting Started](https://hanshannus.github.io/imbrex/guide/getting-started/) — up
  and running in 5 minutes
- [User Guide](https://hanshannus.github.io/imbrex/guide/loading/) — loading,
  merging, priority, env vars, validation
- [Remote Secrets](https://hanshannus.github.io/imbrex/guide/remote-secrets/) —
  descriptor-driven AWS/Azure/GCP loading in `from_dir()`
- [API Reference](https://hanshannus.github.io/imbrex/api/) — auto-generated from source
- [Cookbook & Patterns](https://hanshannus.github.io/imbrex/examples/cookbook/) —
  copy-paste recipes

### Build docs locally

```bash
uv sync
uv run zensical serve        # http://127.0.0.1:8000
```

---

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full development workflow,
including uv, Commitizen, prek hooks, docs, and the release process.

---

## Requirements

- Python ≥ 3.11
- `PyYAML ≥ 6.0` · `python-dotenv ≥ 1.0`
- `pydantic ≥ 2.0` *(optional)*

---

MIT licence
