# Loading Configuration

**strata** provides multiple ways to load configuration data.  Every loader
returns a [`Config`](../api/config.md) object — an immutable, dict-like
container that tracks its sources.

## From files

### Format-specific loaders

```python
from strata import Config

cfg = Config.from_toml("settings.toml")
cfg = Config.from_yaml("settings.yaml")
cfg = Config.from_json("settings.json")
```

### Auto-detect format

`from_file()` infers the format from the file extension:

```python
cfg = Config.from_file("settings.toml")   # same as from_toml()
cfg = Config.from_file("settings.yaml")   # same as from_yaml()
cfg = Config.from_file("settings.json")   # same as from_json()
```

Supported extensions: `.toml`, `.yaml`, `.yml`, `.json`.

### Multiple files

Pass multiple paths to merge them **left to right** — the *last* file wins:

```python
cfg = Config.from_toml("defaults.toml", "production.toml")
```

This is equivalent to:

```python
defaults = Config.from_toml("defaults.toml")
production = Config.from_toml("production.toml")
cfg = Config.merge(defaults, production)
```

You can even mix formats with `from_file()`:

```python
cfg = Config.from_file("defaults.toml", "overrides.yaml", "secrets.json")
```

## From a directory

See the dedicated [Directory & Priority](directory-priority.md) guide for
full details.

```python
cfg = Config.from_dir("config/", extension="toml", env="production")
```

## From plain dicts

Useful for testing, programmatic config, or merging with loaded files:

```python
cfg = Config.from_dict(
    {"database": {"url": "sqlite:///default.db", "pool_size": 5}},
    {"database": {"url": "postgresql://localhost/myapp"}},
)

print(cfg["database"]["url"])       # "postgresql://localhost/myapp"
print(cfg["database"]["pool_size"]) # 5  (kept from first dict)
```

## From raw strings

Parse inline configuration text:

=== "TOML"

    ```python
    cfg = Config.from_string(
        '[cache]\nbackend = "redis"\nttl = 300',
        fmt="toml",
    )
    ```

=== "YAML"

    ```python
    cfg = Config.from_string(
        "cache:\n  backend: redis\n  ttl: 300",
        fmt="yaml",
    )
    ```

=== "JSON"

    ```python
    cfg = Config.from_string(
        '{"cache": {"backend": "redis", "ttl": 300}}',
        fmt="json",
    )
    ```

## From environment variables

`from_env()` reads `os.environ`, strips an optional prefix, and converts
the separator (default `__`) into nested dict keys:

```python
# Given:  APP_DATABASE__URL=postgres://host/db
#         APP_DATABASE__POOL_SIZE=10

cfg = Config.from_env(prefix="APP_")

print(cfg["database"]["url"])       # "postgres://host/db"
print(cfg["database"]["pool_size"]) # "10"  (always a string)
```

!!! warning "Values are always strings"

    Environment variables are plain strings.  Use
    [`Config.validate()`](validation.md) with a Pydantic model to coerce
    types automatically.

### Custom separator

```python
cfg = Config.from_env(prefix="APP_", separator="_")
# APP_DB_URL → {"db": {"url": "..."}}
```

## Merging Config objects

Combine independently-loaded `Config` objects:

```python
base    = Config.from_toml("defaults.toml")
env     = Config.from_toml("production.toml")
secrets = Config.from_env(prefix="APP_")

cfg = Config.merge(base, env, secrets)
```

The *last* config has the highest priority.  See
[Merge Strategies](merge-strategies.md) for controlling how values combine.

## Accessing values

Every `Config` supports dict-like access:

```python
cfg["app"]["name"]              # KeyError if missing
cfg.get("app", {})              # returns default if missing
"database" in cfg               # membership test
len(cfg)                        # number of top-level keys
list(cfg)                       # iterate top-level keys
cfg.to_dict()                   # deep copy as a plain dict
```

### Source tracking

Every `Config` records where its data came from:

```python
cfg.sources
# ['config/defaults.toml', 'config/production.toml']

cfg.data
# The raw merged dict
```

