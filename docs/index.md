---
hide:
  - navigation
---

# imbrex

<p align="center" style="font-size: 1.4em; color: var(--md-default-fg-color--light);">
  <strong>Hierarchical configuration management for Python.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/imbrex/"><img src="https://img.shields.io/pypi/v/imbrex?color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/imbrex/"><img src="https://img.shields.io/pypi/pyversions/imbrex" alt="Python"></a>
  <a href="https://github.com/hanshannus/imbrex/blob/main/LICENSE"><img 
src="https://img.shields.io/github/license/hanshannus/imbrex" alt="License"></a>
</p>

---

Load **YAML**, **TOML**, and **JSON** files — individually or from a directory —
merge them in the correct priority order, and validate the result with
**Pydantic v2**.

```python
from imbrex import Config

cfg = Config.from_dir("config/", extension="toml", env="production")
settings = cfg.validate(AppSettings)
```

## Why imbrex?

Most applications need configuration from multiple sources — sensible defaults,
environment-specific overrides, local developer tweaks, and secrets.  **imbrex**
handles all of this with a single, composable API:

- **Multi-format** — TOML, YAML, and JSON out of the box.
- **Automatic priority ordering** — `defaults → base → dev → staging → prod → local → secrets`.
- **Flexible merge strategies** — replace, additive (list concatenation), or type-safe.
- **Pydantic validation** — validate and get fully-typed settings objects.
- **Dot-path access** — `cfg.get("database.pool_size")` traverses nested dicts and lists.
- **Temporary overrides** — `cfg.override({"app.debug": True})` context manager for tests.
- **Frozen configs** — `cfg.freeze()` or `freeze=True` to lock a Config against accidental mutation.
- **Environment variables** — `APP_DATABASE__URL` becomes `database.url` automatically.
- **Remote secrets** — auto-detect `secrets.*` descriptors for AWS/Azure/GCP in `from_dir()`.
- **Zero config** — works out of the box with sensible defaults, customisable when needed.

## Quick start

```python
from imbrex import Config
from pydantic import BaseModel

class Database(BaseModel):
    url: str
    pool_size: int = 5

class Settings(BaseModel):
    debug: bool = False
    database: Database

# Load a directory — files auto-sorted by environment tier
cfg = Config.from_dir("config/", extension="toml", env="production")

# Validate into a typed settings object
settings = cfg.validate(Settings)
print(settings.database.url)       # postgresql://prod-db:5432/myapp
print(settings.database.pool_size) # 20
```

## At a glance

| Feature | API |
|---|---|
| Single / multiple files | `Config.from_toml()`, `from_yaml()`, `from_json()`, `from_file()` |
| Directory with priority sort | `Config.from_dir("config/", env="production")` |
| Plain dicts | `Config.from_dict(defaults, overrides)` |
| Inline strings | `Config.from_string(text, fmt="toml")` |
| Environment variables | `Config.from_env(prefix="APP_")` |
| Merge Config objects | `Config.merge(base, env, secrets)` |
| Pydantic validation | `cfg.validate(MySettings)` |
| Dict-like access | `cfg["key"]`, `cfg.get("key")`, `"key" in cfg` |
| Dot-path access | `cfg.get("database.pool_size")`, `cfg.get("items.0")` |
| Temporary overrides | `with cfg.override({"app.debug": True}): ...` |
| Frozen / immutable | `cfg.freeze()`, `Config.from_dict(..., freeze=True)` |

---

<div class="grid cards" markdown>

-   **Get started in 5 minutes**

    ---

    Install imbrex with `pip` or `uv` and create your first layered
    configuration.

    [Getting Started](guide/getting-started.md)

-   **User Guide**

    ---

    Deep-dive into loading, merging, priority ordering, environment
    variables, and Pydantic validation.

    [User Guide](guide/loading.md)

-   **API Reference**

    ---

    Complete auto-generated reference for every public class, method,
    and function.

    [API Reference](api/index.md)

-   **Cookbook & Patterns**

    ---

    Copy-paste recipes for common configuration patterns.

    [Cookbook](examples/cookbook.md)

</div>
