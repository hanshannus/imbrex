# Real-World Patterns

Production-tested patterns for structuring configuration with **imbrex**.

---

## Pattern 1 — Directory-per-environment

The most common layout.  Each environment has a dedicated file, and the
directory is loaded with `env=`.

```text
config/
├── defaults.toml       # factory defaults (prio 100)
├── development.toml    # local dev overrides (prio 300)
├── staging.toml        # staging overrides (prio 400)
├── production.toml     # production overrides (prio 500)
├── local.toml          # machine-specific, .gitignored (prio 600)
└── secrets.toml        # sensitive values, .gitignored (prio 700)
```

```python
import os
from imbrex import Config

env = os.getenv("APP_ENV", "development")
cfg = Config.from_dir("config/", extension="toml", env=env)
settings = cfg.validate(AppSettings)
```

`.gitignore`:

```gitignore
config/local.toml
config/secrets.toml
```

---

## Pattern 2 — Twelve-factor app

Keep files for non-sensitive defaults; inject secrets via environment
variables:

```python
from imbrex import Config

# Layer 1: File-based defaults + environment overrides
file_cfg = Config.from_dir("config/", extension="toml", env="production")

# Layer 2: Environment variables (highest priority)
env_cfg = Config.from_env(prefix="APP_")

# Merge — env vars win
cfg = Config.merge(file_cfg, env_cfg)
settings = cfg.validate(AppSettings)
```

Set environment variables in your deployment:

```bash
APP_DATABASE__URL="postgresql://prod-host:5432/myapp"
APP_DATABASE__POOL_SIZE="20"
APP_SECRET_KEY="super-secret-value"
```

---

## Pattern 3 — Shared base with per-service overrides

Monorepo with multiple services sharing a common configuration:

```text
config/
├── base.toml           # shared across all services
├── api/
│   ├── defaults.toml
│   └── production.toml
└── worker/
    ├── defaults.toml
    └── production.toml
```

```python
base = Config.from_toml("config/base.toml")
service = Config.from_dir(
    "config/api/",
    extension="toml",
    env="production",
)
cfg = Config.merge(base, service)
```

---

## Pattern 4 — Testing with inline config

Create deterministic test configurations without touching the filesystem:

```python
import pytest
from imbrex import Config

@pytest.fixture()
def app_config():
    return Config.from_dict({
        "app": {"debug": True, "name": "TestApp"},
        "database": {
            "url": "sqlite:///:memory:",
            "pool_size": 1,
        },
    })

def test_database_url(app_config):
    assert app_config["database"]["url"] == "sqlite:///:memory:"
```

Or use inline TOML/YAML:

```python
@pytest.fixture()
def app_config():
    return Config.from_string("""
        [app]
        debug = true
        name  = "TestApp"

        [database]
        url       = "sqlite:///:memory:"
        pool_size = 1
    """, fmt="toml")
```

---

## Pattern 5 — Feature flags

Use a dedicated section for feature flags, with additive list merge for
experiments:

```toml
# defaults.toml
[features]
enabled  = ["dark_mode"]
disabled = ["beta_ui"]
```

```toml
# production.toml
[features]
enabled = ["cdn_assets"]
```

```python
from imbrex import Config, MergeStrategy

cfg = Config.from_dir(
    "config/",
    extension="toml",
    env="production",
    key_strategies={"features.enabled": MergeStrategy.ADDITIVE},
)

print(cfg["features"]["enabled"])
# ["dark_mode", "cdn_assets"]
```

---

## Pattern 6 — Config validation in CI

Add a CI step that validates configuration files without running the app:

```yaml
# .github/workflows/validate-config.yml
name: Validate Config
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run python -c "
          from imbrex import Config, MergeStrategy;
          cfg = Config.from_dir('config/', extension='toml',
                                merge_strategy=MergeStrategy.TYPESAFE);
          cfg.validate(AppSettings);
          print('✓ Config is valid')
        "
```

Using `TYPESAFE` catches accidental type changes between environment files.

---

## Pattern 7 — Django settings

Use **imbrex** as the settings loader for Django:

```python
# settings.py
import os
from imbrex import Config
from pydantic import BaseModel, Field

class DjangoSettings(BaseModel):
    debug: bool = False
    secret_key: str
    allowed_hosts: list[str] = Field(default_factory=list)
    database_url: str = "sqlite:///db.sqlite3"

env = os.getenv("DJANGO_ENV", "development")

file_cfg = Config.from_dir("config/", extension="toml", env=env)
env_cfg  = Config.from_env(prefix="DJANGO_")
cfg      = Config.merge(file_cfg, env_cfg)

settings = cfg.validate(DjangoSettings)

# Django settings
DEBUG        = settings.debug
SECRET_KEY   = settings.secret_key
ALLOWED_HOSTS = settings.allowed_hosts
```

---

## Pattern 8 — FastAPI / Starlette

```python
# config.py
from functools import lru_cache
from imbrex import Config
from pydantic import BaseModel

class Settings(BaseModel):
    debug: bool = False
    database_url: str
    redis_url: str = "redis://localhost:6379"

@lru_cache
def get_settings() -> Settings:
    file_cfg = Config.from_dir("config/", extension="toml", env="production")
    env_cfg  = Config.from_env(prefix="APP_")
    cfg      = Config.merge(file_cfg, env_cfg)
    return cfg.validate(Settings)
```

```python
# main.py
from fastapi import Depends, FastAPI
from config import Settings, get_settings

app = FastAPI()

@app.get("/info")
def info(settings: Settings = Depends(get_settings)):
    return {"debug": settings.debug}
```

---

## Anti-patterns to avoid

!!! danger "Don't commit secrets"

    Never commit `secrets.toml` or `local.toml` to version control.  Add
    them to `.gitignore` and use environment variables in production.

!!! warning "Don't use ADDITIVE globally"

    `MergeStrategy.ADDITIVE` concatenates *all* lists.  Use it only as a
    per-key override for specific list fields like `allowed_hosts`.

!!! warning "Don't skip validation"

    Always validate your merged config with a Pydantic model before using it.
    This catches missing fields, wrong types, and structural errors before
    they cause runtime bugs.

