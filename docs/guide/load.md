# One-Call Loading

`imbrex.load()` is the shortest path from "files and environment" to a
validated settings object.

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

## Precedence

Sources are merged in a fixed order. **Later sources win**:

| # | Source | Used when |
|---|---|---|
| 1 | Files in `directory`, ordered by [environment tier](directory-priority.md) | `directory` is given |
| 2 | The `.env` file | `dotenv` is not `None` and the file exists |
| 3 | Real environment variables starting with `env_prefix` | `env_prefix` is not empty |
| 4 | `overrides={...}` | `overrides` is given |

!!! note "Real environment variables need a prefix"

    `load()` only reads environment variables when you pass `env_prefix`.
    Without it, unrelated variables such as `PATH` or `HOME` would end up in
    your settings. The `.env` file is an explicit file, so it is read in full.

## Types are coerced

Values from `.env` and from the environment are converted before validation:
`true`/`false` become `bool`, integers become `int`, decimals become `float`,
and `[...]` / `{...}` are parsed as JSON. Anything else stays a string, so
`007` and `1e3` are left alone.

```bash
APP_DEBUG=true
APP_DATABASE__POOL_SIZE=20
APP_ALLOWED_HOSTS=["a.example.com", "b.example.com"]
```

## Options

| Argument | Default | Meaning |
|---|---|---|
| `schema` | – | Pydantic model to validate against. `None` returns the raw `Config`. |
| `directory` | `None` | Config directory. `None` skips files. |
| `env` | `None` | Environment tier. Falls back to `APP_ENV`, `ENV`, `ENVIRONMENT`. |
| `env_prefix` | `""` | Prefix of the environment variables to read. |
| `dotenv` | `".env"` | Dotenv file. A missing file is ignored. `None` disables it. |
| `extension` | auto | `"toml"`, `"yaml"` or `"json"`. |
| `overrides` | `None` | Highest-priority values, for example from CLI flags. |
| `secrets_ttl` | `None` | Cache fetched [remote secrets](remote-secrets.md#caching-and-refreshing) for this many seconds. |
| `interpolate` | `True` | Resolve [`${...}` references](interpolation.md) after merging. |

### File format detection

When the directory contains a single format, `load()` uses it. If it mixes
formats, `load()` raises an error and asks you to pass `extension=...`.

## `load_config()`: when you need the `Config`

`load_config()` accepts the same arguments (except `schema`) and returns the
merged [`Config`](../api/config.md). Use it for [`explain()`](provenance.md)
or when you want to validate later:

```python
cfg = imbrex.load_config("config/", env="production", env_prefix="APP_")
print(cfg.explain("database.url"))
settings = cfg.validate(Settings)
```

## Reloading

`load_config()` results remember how they were built:
`cfg = cfg.reload()` re-reads files, `.env`, environment variables and
secrets and returns a new `Config`. See
[Caching and refreshing](remote-secrets.md#caching-and-refreshing).

## Building blocks

`load()` is a thin composition of the lower-level loaders. Reach for them when
you need a different order or extra sources:

```python
layers = [
    Config.from_dir("config/", extension="toml", env="production"),
    Config.from_dotenv(".env", prefix="APP_", coerce=True, required=False),
    Config.from_env(prefix="APP_", coerce=True),
]
cfg = Config.merge(*layers)
```
