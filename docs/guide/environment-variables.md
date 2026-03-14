# Environment Variables

**imbrex** can build configuration from environment variables, making it
easy to inject secrets or platform-specific values in containers and CI.

## Basic usage

```python
from imbrex import Config

cfg = Config.from_env(prefix="APP_")
```

### How it works

1. **Filter** — only variables starting with the prefix are included.
2. **Strip** — the prefix is removed from each variable name.
3. **Lower-case** — the remaining name is converted to lowercase.
4. **Nest** — the separator (default `__`) splits the name into nested
   dict keys.

### Example

```bash
export APP_DATABASE__URL="postgresql://host/db"
export APP_DATABASE__POOL_SIZE="20"
export APP_DEBUG="true"
export UNRELATED_VAR="ignored"
```

```python
cfg = Config.from_env(prefix="APP_")
```

Resulting data:

```python
{
    "database": {
        "url": "postgresql://host/db",
        "pool_size": "20",
    },
    "debug": "true",
}
```

!!! warning "All values are strings"

    Environment variables are always strings.  Use `Config.validate()` with a
    Pydantic model to coerce `"20"` → `20` and `"true"` → `True`
    automatically:

    ```python
    from pydantic import BaseModel

    class Settings(BaseModel):
        debug: bool = False
        database: DatabaseSettings

    settings = cfg.validate(Settings)  # types are coerced
    ```

## Custom separator

Change the nesting separator:

```python
cfg = Config.from_env(prefix="APP_", separator="_")
# APP_DB_URL → {"db": {"url": "..."}}
```

## No prefix

Omit the prefix to include **all** environment variables (rarely recommended):

```python
cfg = Config.from_env()
```

## Combining with file-based config

A common pattern is to layer environment variables on top of file-based
configuration:

```python
file_cfg = Config.from_dir("config/", extension="toml", env="production")
env_cfg  = Config.from_env(prefix="APP_")

cfg = Config.merge(file_cfg, env_cfg)
# Environment variables override file-based values
```

This follows the [twelve-factor app](https://12factor.net/config) principle
of keeping secrets out of files.

## Environment detection

**imbrex** also reads environment variables to detect the *active environment*
when loading directories.  The following variables are checked in order:

| Variable | Example |
|---|---|
| `APP_ENV` | `production` |
| `ENV` | `staging` |
| `ENVIRONMENT` | `development` |

When `env=` is passed explicitly to `from_dir()` or `sort_paths()`, it takes
precedence over all environment variables.

## Source tracking

```python
cfg = Config.from_env(prefix="APP_")
print(cfg.sources)
# ["<env prefix='APP_'>"]
```

