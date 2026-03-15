# Loading Configuration

**imbrex** provides multiple ways to load configuration data.  Every loader
returns a [`Config`](../api/config.md) object — an immutable, dict-like
container that tracks its sources.

## From files

### Format-specific loaders

```python
from imbrex import Config

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

`from_dir()` can also auto-detect secret descriptor files (`secrets.*`,
`.secrets.*`) and fetch remote provider values (AWS/Azure/GCP) before
returning one merged config object.

See [Remote Secrets in from_dir()](remote-secrets.md).

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

### Dot-path access with `get()`

`Config.get()` accepts dot-separated paths to reach deeply nested values,
including list indices:

```python
cfg = Config.from_dict({
    "database": {"url": "sqlite:///app.db", "pool_size": 10},
    "server": {
        "host": "localhost",
        "allowed_hosts": ["myapp.com", "localhost"],
    },
})

cfg.get("database.pool_size")       # 10
cfg.get("server.allowed_hosts.0")   # "myapp.com"
cfg.get("server")                   # full dict
cfg.get("missing.key", "fallback")  # "fallback"
cfg.get("missing.key")              # raises KeyError
```

Falsy values (`None`, `False`, `0`, `""`) are returned correctly — the
default is only used when the path does not exist at all:

```python
cfg = Config.from_dict({"flag": False, "count": 0})
cfg.get("flag", True)    # False  (not replaced)
cfg.get("count", 99)     # 0      (not replaced)
```

## Temporary overrides

Use the `override()` context manager to temporarily patch values — ideal for
tests:

```python
cfg = Config.from_dict({"app": {"debug": False, "workers": 4}})

with cfg.override({"app.debug": True, "app.workers": 1}):
    assert cfg.get("app.debug") is True
    assert cfg.get("app.workers") == 1

# Original values are automatically restored
assert cfg.get("app.debug") is False
assert cfg.get("app.workers") == 4
```

Overrides are always restored, even when an exception occurs inside the
`with` block.

!!! note "Override creates new keys"

    You can inject keys that didn't exist before:

    ```python
    with cfg.override({"app.new_key": "injected"}):
        assert cfg.get("app.new_key") == "injected"
    # key is removed on exit
    ```

## Frozen / immutable configs

Lock a `Config` instance so any mutation attempt raises `FrozenConfigError`
at runtime.  This prevents accidental writes in production code.

### Freeze at construction

Every factory method accepts `freeze=True`:

```python
cfg = Config.from_dir("config/", extension="toml", env="production", freeze=True)
cfg = Config.from_toml("settings.toml", freeze=True)
cfg = Config.from_dict({"key": "value"}, freeze=True)
cfg = Config.from_env(prefix="APP_", freeze=True)
cfg = Config.merge(base, env, freeze=True)
```

### Freeze after construction

```python
cfg = Config.from_dir("config/", extension="toml")
# ... do any setup mutations ...
cfg.freeze()  # returns self, so chaining works:
cfg = Config.from_dict({"key": "value"}).freeze()
```

### What's blocked?

```python
from imbrex import FrozenConfigError

cfg = Config.from_dict({"app": {"debug": False}}, freeze=True)

# override() is blocked
with cfg.override({"app.debug": True}):  # ❌ FrozenConfigError
    ...

# Direct _data assignment is blocked
cfg._data = {}  # ❌ FrozenConfigError
```

### Read access is unaffected

All read operations work normally on a frozen config:

```python
cfg.get("app.debug")        # ✅
cfg["app"]                  # ✅
"app" in cfg                # ✅
cfg.to_dict()               # ✅ (returns a deep copy)
cfg.validate(MySettings)    # ✅
cfg.data                    # ✅
cfg.sources                 # ✅
```

### Unfreeze

If you need to mutate again (e.g. in tests), call `unfreeze()`:

```python
cfg.unfreeze()
with cfg.override({"app.debug": True}):
    ...  # works now
cfg.freeze()  # re-lock
```

### Source tracking

Every `Config` records where its data came from:

```python
cfg.sources
# ['config/defaults.toml', 'config/production.toml']

cfg.data
# The raw merged dict
```
