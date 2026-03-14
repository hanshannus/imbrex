# Pydantic Validation

**imbrex** integrates with [Pydantic v2](https://docs.pydantic.dev/) to
validate merged configuration and produce fully-typed settings objects.

!!! note "Pydantic is optional"

    Install with `pip install "imbrex[pydantic]"` or `uv add "imbrex[pydantic]"`.
    If Pydantic is not installed, `Config.validate()` falls back to calling
    `schema(**data)`.

## Basic validation

```python
from pydantic import BaseModel
from imbrex import Config

class Settings(BaseModel):
    debug: bool = False
    workers: int = 1
    name: str

cfg = Config.from_dict({"name": "MyApp", "debug": True, "workers": 4})
settings = cfg.validate(Settings)

print(type(settings))   # <class 'Settings'>
print(settings.name)    # "MyApp"
print(settings.debug)   # True
print(settings.workers) # 4
```

## Nested models

Define a hierarchy of models to validate deeply nested configuration:

```python
from pydantic import BaseModel, Field

class DatabaseSettings(BaseModel):
    url: str
    pool_size: int = 5
    echo: bool = False

class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    allowed_hosts: list[str] = Field(default_factory=list)

class AppSettings(BaseModel):
    debug: bool = False
    database: DatabaseSettings
    server: ServerSettings = Field(default_factory=ServerSettings)
```

```python
cfg = Config.from_dir("config/", extension="toml", env="production")
settings = cfg.validate(AppSettings)

print(settings.database.url)       # "postgresql://prod-db:5432/myapp"
print(settings.database.pool_size) # 20
print(settings.server.host)        # "0.0.0.0"
```

## Default values

Pydantic fields with defaults are populated automatically when the config
doesn't provide them:

```python
cfg = Config.from_dict({"name": "Minimal"})
settings = cfg.validate(Settings)

print(settings.debug)   # False  (default)
print(settings.workers) # 1      (default)
```

## Type coercion

Pydantic automatically coerces compatible types.  This is especially useful
with environment variables (which are always strings):

```python
cfg = Config.from_env(prefix="APP_")
# {"debug": "true", "workers": "4", "name": "MyApp"}

settings = cfg.validate(Settings)
print(settings.debug)   # True  (str → bool)
print(settings.workers) # 4     (str → int)
```

## Error handling

When validation fails, imbrex raises
[`ConfigValidationError`](../api/exceptions.md) with the original Pydantic
error and the raw data:

```python
from imbrex import Config
from imbrex._exceptions import ConfigValidationError

cfg = Config.from_dict({"debug": True})  # missing required 'name'

try:
    settings = cfg.validate(Settings)
except ConfigValidationError as exc:
    print(exc)          # "Validation failed: ..."
    print(exc.cause)    # Original Pydantic ValidationError
    print(exc.data)     # {"debug": True}
```

### Common validation errors

| Error | Cause | Fix |
|---|---|---|
| Missing required field | A field without a default is not in the config | Add the field to your config or set a default |
| Wrong type | Value type doesn't match the model field | Fix the config or use a `Union` type |
| Extra fields | Model uses `extra = "forbid"` and config has unknown keys | Remove the key or change the model config |

## Strict models

Use Pydantic's `model_config` to forbid extra fields:

```python
class StrictSettings(BaseModel):
    model_config = {"extra": "forbid"}

    name: str
    debug: bool = False

cfg = Config.from_dict({"name": "X", "unknown": 123})

try:
    cfg.validate(StrictSettings)
except ConfigValidationError:
    print("Extra fields are not allowed!")
```

## Using dict-like models

For sections where you want flexible keys, use `dict` as the field type:

```python
from typing import Any

class FlexSettings(BaseModel):
    app: dict[str, Any]                # accept anything
    database: DatabaseSettings         # strictly validated
```

## Full example

```python
from pathlib import Path
from pydantic import BaseModel, Field
from imbrex import Config, MergeStrategy
from typing import Any

class DatabaseSettings(BaseModel):
    url: str
    pool_size: int = 5
    echo: bool = False

class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    allowed_hosts: list[str] = Field(default_factory=list)

class LoggingSettings(BaseModel):
    level: str = "INFO"

class AppSettings(BaseModel):
    app: dict[str, Any] = Field(default_factory=dict)
    database: DatabaseSettings
    server: ServerSettings = Field(default_factory=ServerSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


# Load from directory with additive list merge for allowed_hosts
cfg = Config.from_dir(
    "config/",
    extension="toml",
    env="production",
    key_strategies={"server.allowed_hosts": MergeStrategy.ADDITIVE},
)

# Validate — fully typed, IDE-friendly settings object
settings = cfg.validate(AppSettings)

print(settings.database.url)            # postgresql://prod-db:5432/myapp
print(settings.server.allowed_hosts)    # ["localhost", "myapp.com", ...]
print(settings.logging.level)           # WARNING
```
