"""
examples/usage.py — runnable imbrex demo.

    python examples/usage.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# ── make the package importable without installing ─────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from imbrex import Config, MergeStrategy

# ── helpers ────────────────────────────────────────────────────────────────


def banner(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


def write_configs(d: Path) -> None:
    (d / "defaults.toml").write_bytes(b"""\
[app]
name    = "MyApp"
debug   = false
workers = 2

[database]
url       = "sqlite:///app.db"
pool_size = 5
echo      = false

[server]
host          = "127.0.0.1"
port          = 8000
allowed_hosts = ["localhost"]

[logging]
level = "INFO"
""")
    (d / "development.toml").write_bytes(b"""\
[app]
debug   = true
workers = 1

[database]
url  = "postgresql://localhost/myapp_dev"
echo = true

[server]
allowed_hosts = ["localhost", "127.0.0.1"]

[logging]
level = "DEBUG"
""")
    (d / "production.toml").write_bytes(b"""\
[app]
debug   = false
workers = 8

[database]
url       = "postgresql://prod-db:5432/myapp"
pool_size = 20

[server]
host          = "0.0.0.0"
port          = 80
allowed_hosts = ["myapp.com", "www.myapp.com"]

[logging]
level = "WARNING"
""")


# ── examples ───────────────────────────────────────────────────────────────

with tempfile.TemporaryDirectory() as _td:
    config_dir = Path(_td)
    write_configs(config_dir)

    # ── 1. Single file ─────────────────────────────────────────────────
    banner("1 · from_toml — single file")
    cfg = Config.from_toml(config_dir / "defaults.toml")
    print(f"  cfg.data['app']      = {cfg['app']}")
    print(f"  cfg.sources          = {cfg.sources}")

    # ── 2. Multiple files (explicit order) ─────────────────────────────
    banner("2 · from_toml — multiple files (explicit order)")
    cfg = Config.from_toml(
        config_dir / "defaults.toml",
        config_dir / "production.toml",
    )
    print(f"  app.debug   = {cfg['app']['debug']}")  # False (prod)
    print(f"  app.workers = {cfg['app']['workers']}")  # 8     (prod)
    print(f"  db.url      = {cfg['database']['url']}")  # prod url
    print(f"  db.pool     = {cfg['database']['pool_size']}")  # 20  (prod)

    # ── 3. from_dir — auto hierarchical sort (development env) ─────────
    banner("3 · from_dir — development environment (auto-sort)")
    cfg = Config.from_dir(config_dir, extension="toml", env="development")
    print(f"  app.debug   = {cfg['app']['debug']}")  # True   (dev overrides)
    print(f"  app.workers = {cfg['app']['workers']}")  # 1      (dev)
    print(f"  db.url      = {cfg['database']['url']}")  # pg dev url
    print(
        f"  db.pool     = {cfg['database']['pool_size']}"
    )  # 5 (defaults, not overridden by dev)
    print(f"  log.level   = {cfg['logging']['level']}")  # DEBUG  (dev)
    print(f"  sources     = {[Path(s).name for s in cfg.sources]}")

    # ── 4. from_dir — production env ───────────────────────────────────
    banner("4 · from_dir — production environment")
    cfg = Config.from_dir(config_dir, extension="toml", env="production")
    print(f"  app.debug   = {cfg['app']['debug']}")  # False
    print(f"  app.workers = {cfg['app']['workers']}")  # 8
    print(f"  db.pool     = {cfg['database']['pool_size']}")  # 20
    print(f"  log.level   = {cfg['logging']['level']}")  # WARNING
    print(f"  sources     = {[Path(s).name for s in cfg.sources]}")

    # ── 5. from_dir — explicit order ───────────────────────────────────
    banner("5 · from_dir — explicit stem order")
    cfg = Config.from_dir(
        config_dir,
        extension="toml",
        order=["defaults", "production"],  # skip development entirely
    )
    print(f"  app.debug   = {cfg['app']['debug']}")  # False (prod)
    print(f"  db.url      = {cfg['database']['url']}")  # prod url

    # ── 6. from_dict ───────────────────────────────────────────────────
    banner("6 · from_dict — plain dicts")
    cfg = Config.from_dict(
        {"database": {"url": "sqlite:///default.db", "pool_size": 5}},
        {"database": {"url": "postgresql://localhost/myapp"}},  # overrides url
    )
    print(f"  db.url      = {cfg['database']['url']}")  # pg url
    print(f"  db.pool     = {cfg['database']['pool_size']}")  # 5 (kept from first dict)

    # ── 7. from_string ─────────────────────────────────────────────────
    banner("7 · from_string — inline TOML")
    toml_text = '[cache]\nbackend = "redis"\nttl     = 300\n'
    cfg = Config.from_string(toml_text, fmt="toml")
    print(f"  cache.backend = {cfg['cache']['backend']}")
    print(f"  cache.ttl     = {cfg['cache']['ttl']}")

    # ── 8. from_string — inline YAML ───────────────────────────────────
    banner("8 · from_string — inline YAML")
    yaml_text = "feature_flags:\n  dark_mode: true\n  beta: false\n"
    cfg = Config.from_string(yaml_text, fmt="yaml")
    print(f"  feature_flags = {cfg['feature_flags']}")

    # ── 9. from_env ────────────────────────────────────────────────────
    banner("9 · from_env — environment variables")
    os.environ["APP_DATABASE__URL"] = "postgresql://envhost/myapp"
    os.environ["APP_DATABASE__POOL_SIZE"] = "30"
    os.environ["APP_DEBUG"] = "true"
    cfg = Config.from_env(prefix="APP_")
    print(f"  database.url       = {cfg['database']['url']}")
    print(f"  database.pool_size = {cfg['database']['pool_size']}")
    print(f"  debug              = {cfg['debug']}")

    # ── 10. Config.merge ───────────────────────────────────────────────
    banner("10 · Config.merge — combine existing Config objects")
    base_cfg = Config.from_toml(config_dir / "defaults.toml")
    env_cfg = Config.from_toml(config_dir / "development.toml")
    merged = Config.merge(base_cfg, env_cfg)
    print(f"  app.debug   = {merged['app']['debug']}")  # True (dev wins)
    print(f"  app.name    = {merged['app']['name']}")  # MyApp (from defaults)

    # ── 11. ADDITIVE list merge ────────────────────────────────────────
    banner("11 · MergeStrategy.ADDITIVE — lists concatenated")
    cfg = Config.from_dir(
        config_dir,
        extension="toml",
        env="production",
        key_strategies={"server.allowed_hosts": MergeStrategy.ADDITIVE},
    )
    print(f"  server.allowed_hosts = {cfg['server']['allowed_hosts']}")
    # ["localhost"] + ["myapp.com", "www.myapp.com"]

    # ── 12. Pydantic validation ────────────────────────────────────────
    banner("12 · validate — Pydantic schema")
    try:

        class DatabaseSettings(BaseModel):
            url: str
            pool_size: int = 5
            echo: bool = False

        class ServerSettings(BaseModel):
            host: str = "127.0.0.1"
            port: int = 8000
            allowed_hosts: list[str] = Field(default_factory=list)

        class AppSettings(BaseModel):
            app: dict[str, Any] = Field(default_factory=dict)
            database: DatabaseSettings
            server: ServerSettings
            logging: dict[str, Any] = Field(default_factory=dict)

        cfg = Config.from_dir(config_dir, extension="toml", env="development")
        settings = cfg.validate(AppSettings)

        print(f"  type(settings)          = {type(settings).__name__}")
        print(f"  settings.database.url   = {settings.database.url}")
        print(f"  settings.database.pool  = {settings.database.pool_size}")
        print(f"  settings.server.host    = {settings.server.host}")
        print(f"  settings.server.port    = {settings.server.port}")

    except ImportError:
        print("  [skipped — pydantic not installed; install with: uv add pydantic]")

print(f"\n{'─' * 60}")
print("  All examples completed ✓")
print("─" * 60)
