# strata

**Hierarchical configuration management for Python.**

Load YAML, TOML, and JSON — individually or from a directory — merge them in
the correct priority order (`defaults → dev → staging → production → local`),
and validate the result with Pydantic v2.

```
uv add strata
uv add strata[pydantic]   # include Pydantic v2
```

---

## Quick start

```python
from strata import Config

# load a directory, auto-sorted by environment tier
cfg = Config.from_dir("config/", extension="toml", env="production")

# validate with Pydantic
from pydantic import BaseModel

class Database(BaseModel):
    url: str
    pool_size: int = 5

class Settings(BaseModel):
    debug: bool = False
    database: Database

settings = cfg.validate(Settings)
print(settings.database.url)
print(settings.database.pool_size)
```

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
```

### Merge Config objects

```python
merged = Config.merge(base_cfg, env_cfg, secret_cfg)
```

---

## Merge strategies

```python
from strata import MergeStrategy

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

## Requirements

- Python ≥ 3.11  
- `PyYAML ≥ 6.0` · `mergedeep ≥ 1.3` · `python-dotenv ≥ 1.0`  
- `pydantic ≥ 2.0` *(optional)*

---

MIT licence
