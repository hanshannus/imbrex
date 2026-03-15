# Getting Started

This guide walks you through your first **imbrex** configuration in under
five minutes.

## 1. Install imbrex

=== "uv"

    ```bash
    uv add "imbrex[pydantic]"
    ```

=== "pip"

    ```bash
    pip install "imbrex[pydantic]"
    ```

## 2. Create configuration files

Create a `config/` directory with two TOML files:

```text
config/
├── defaults.toml
└── production.toml
```

**`config/defaults.toml`** — sensible defaults for every environment:

```toml
[app]
name    = "MyApp"
debug   = false
workers = 2

[database]
url       = "sqlite:///app.db"
pool_size = 5
```

**`config/production.toml`** — production overrides:

```toml
[app]
workers = 8

[database]
url       = "postgresql://prod-db:5432/myapp"
pool_size = 20
```

## 3. Load and merge

```python
from imbrex import Config

cfg = Config.from_dir("config/", extension="toml", env="production")

print(cfg["app"]["name"])          # "MyApp"      ← from defaults
print(cfg["app"]["workers"])       # 8             ← overridden by production
print(cfg["database"]["url"])      # "postgresql://prod-db:5432/myapp"
print(cfg["database"]["pool_size"])# 20
```

**imbrex** discovers every `.toml` file in the directory, sorts them by the
built-in [priority table](directory-priority.md), filters out files above
the active environment tier, and deep-merges them left to right.

## 4. Validate with Pydantic

Define your settings schema as Pydantic models:

```python
from pydantic import BaseModel

class DatabaseSettings(BaseModel):
    url: str
    pool_size: int = 5

class AppSettings(BaseModel):
    app: dict
    database: DatabaseSettings
```

Validate:

```python
settings = cfg.validate(AppSettings)

print(type(settings))              # <class 'AppSettings'>
print(settings.database.url)       # "postgresql://prod-db:5432/myapp"
print(settings.database.pool_size) # 20
```

If any required field is missing or has the wrong type, imbrex raises
[`ConfigValidationError`](../api/exceptions.md) with the full Pydantic
error details.

## 5. What's next?

| Topic | Description |
|---|---|
| [Loading Configuration](loading.md) | All the ways to load config: files, strings, dicts, env vars |
| [Directory & Priority](directory-priority.md) | How the automatic tier ordering works |
| [Merge Strategies](merge-strategies.md) | REPLACE vs ADDITIVE vs TYPESAFE |
| [Environment Variables](environment-variables.md) | `APP_DATABASE__URL` → `database.url` |
| [Remote Secrets](remote-secrets.md) | Auto-detect `secrets.*` and fetch AWS/Azure/GCP in `from_dir()` |
| [Pydantic Validation](validation.md) | Nested models, strict mode, error handling |
| [Cookbook](../examples/cookbook.md) | Ready-to-use recipes |
