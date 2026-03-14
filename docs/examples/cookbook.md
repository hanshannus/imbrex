# Cookbook

Copy-paste recipes for common configuration tasks.

## Load a single TOML file

```python
from imbrex import Config

cfg = Config.from_toml("settings.toml")
print(cfg["database"]["url"])
```

## Load and merge multiple files

```python
cfg = Config.from_toml("defaults.toml", "production.toml")
# production.toml values override defaults.toml
```

## Load from a directory with environment filtering

```python
cfg = Config.from_dir("config/", extension="toml", env="production")
```

Files above the `production` tier (`local.toml`, `secrets.toml`) are
automatically excluded.

## Concatenate lists across layers

```python
from imbrex import Config, MergeStrategy

cfg = Config.from_toml(
    "defaults.toml",     # allowed_hosts = ["localhost"]
    "production.toml",   # allowed_hosts = ["myapp.com"]
    key_strategies={"server.allowed_hosts": MergeStrategy.ADDITIVE},
)

print(cfg["server"]["allowed_hosts"])
# ["localhost", "myapp.com"]
```

## Catch type mismatches in CI

```python
from imbrex import Config, MergeStrategy

cfg = Config.from_dir(
    "config/",
    extension="toml",
    merge_strategy=MergeStrategy.TYPESAFE,
)
# Raises TypeError if any key changes type across files
```

## Layer environment variables on top of files

```python
import os
os.environ["APP_DATABASE__URL"] = "postgresql://secret-host/db"

file_cfg = Config.from_dir("config/", extension="toml", env="production")
env_cfg  = Config.from_env(prefix="APP_")

cfg = Config.merge(file_cfg, env_cfg)
# env vars win (highest priority)
print(cfg["database"]["url"])  # "postgresql://secret-host/db"
```

## Validate into typed settings

```python
from pydantic import BaseModel
from imbrex import Config

class Database(BaseModel):
    url: str
    pool_size: int = 5

class Settings(BaseModel):
    debug: bool = False
    database: Database

cfg = Config.from_dir("config/", extension="toml", env="production")
settings = cfg.validate(Settings)

assert isinstance(settings, Settings)
assert isinstance(settings.database, Database)
```

## Handle validation errors gracefully

```python
from imbrex import Config
from imbrex._exceptions import ConfigValidationError

cfg = Config.from_dict({"debug": True})  # missing 'database'

try:
    settings = cfg.validate(Settings)
except ConfigValidationError as exc:
    print(f"Config is invalid: {exc}")
    print(f"Raw data: {exc.data}")
    print(f"Pydantic errors: {exc.cause}")
```

## Load inline YAML for testing

```python
cfg = Config.from_string("""
database:
  url: "sqlite:///:memory:"
  pool_size: 1
app:
  debug: true
""", fmt="yaml")
```

## Load inline TOML for testing

```python
cfg = Config.from_string("""
[database]
url = "sqlite:///:memory:"
pool_size = 1

[app]
debug = true
""", fmt="toml")
```

## Load inline JSON for testing

```python
import json
cfg = Config.from_string(json.dumps({
    "database": {"url": "sqlite:///:memory:", "pool_size": 1},
    "app": {"debug": True},
}), fmt="json")
```

## Use from_dict for test fixtures

```python
def make_test_config(**overrides):
    defaults = {
        "database": {"url": "sqlite:///:memory:", "pool_size": 1},
        "app": {"debug": True, "name": "TestApp"},
    }
    return Config.from_dict(defaults, overrides)

cfg = make_test_config(app={"debug": False})
```

## Inspect sources for debugging

```python
cfg = Config.from_dir("config/", extension="toml", env="production")
print(cfg.sources)
# ['config/defaults.toml', 'config/base.toml', 'config/production.toml']
```

## Get a deep copy of the data

```python
raw = cfg.to_dict()
raw["database"]["url"] = "modified"  # doesn't affect the Config
assert cfg["database"]["url"] != "modified"
```

## Custom priority for a special tier

```python
cfg = Config.from_dir(
    "config/",
    extension="toml",
    env="canary",
    priority_table={"canary": 450},
)
```

## Mix formats with from_file

```python
cfg = Config.from_file(
    "defaults.toml",
    "overrides.yaml",
    "secrets.json",
)
```

## Recursive directory loading

```python
cfg = Config.from_dir(
    "config/",
    extension="yaml",
    recursive=True,
    env="production",
)
```
