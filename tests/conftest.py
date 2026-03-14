"""Shared fixtures for strata tests."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    """Return a clean temporary directory."""
    return tmp_path


@pytest.fixture()
def toml_file(tmp_path: Path) -> Path:
    """Write a simple TOML file and return its path."""
    p = tmp_path / "settings.toml"
    p.write_text(
        textwrap.dedent("""\
            [app]
            name = "TestApp"
            debug = false
            workers = 2

            [database]
            url = "sqlite:///app.db"
            pool_size = 5
        """),
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def yaml_file(tmp_path: Path) -> Path:
    """Write a simple YAML file and return its path."""
    p = tmp_path / "settings.yaml"
    p.write_text(
        textwrap.dedent("""\
            app:
              name: TestApp
              debug: false
              workers: 2
            database:
              url: "sqlite:///app.db"
              pool_size: 5
        """),
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def json_file(tmp_path: Path) -> Path:
    """Write a simple JSON file and return its path."""
    import json

    p = tmp_path / "settings.json"
    data = {
        "app": {"name": "TestApp", "debug": False, "workers": 2},
        "database": {"url": "sqlite:///app.db", "pool_size": 5},
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """Create a directory with defaults, development, and production TOML files."""
    d = tmp_path / "config"
    d.mkdir()

    (d / "defaults.toml").write_text(
        textwrap.dedent("""\
            [app]
            name = "MyApp"
            debug = false
            workers = 2

            [database]
            url = "sqlite:///app.db"
            pool_size = 5

            [server]
            host = "127.0.0.1"
            port = 8000
            allowed_hosts = ["localhost"]

            [logging]
            level = "INFO"
        """),
        encoding="utf-8",
    )

    (d / "development.toml").write_text(
        textwrap.dedent("""\
            [app]
            debug = true
            workers = 1

            [database]
            url = "postgresql://localhost/myapp_dev"

            [server]
            allowed_hosts = ["localhost", "127.0.0.1"]

            [logging]
            level = "DEBUG"
        """),
        encoding="utf-8",
    )

    (d / "production.toml").write_text(
        textwrap.dedent("""\
            [app]
            debug = false
            workers = 8

            [database]
            url = "postgresql://prod-db:5432/myapp"
            pool_size = 20

            [server]
            host = "0.0.0.0"
            port = 80
            allowed_hosts = ["myapp.com", "www.myapp.com"]

            [logging]
            level = "WARNING"
        """),
        encoding="utf-8",
    )

    return d


@pytest.fixture()
def yaml_config_dir(tmp_path: Path) -> Path:
    """Create a directory with defaults and development YAML files."""
    d = tmp_path / "yaml_config"
    d.mkdir()

    (d / "defaults.yaml").write_text(
        textwrap.dedent("""\
            app:
              name: MyApp
              debug: false
            database:
              url: "sqlite:///app.db"
        """),
        encoding="utf-8",
    )

    (d / "development.yaml").write_text(
        textwrap.dedent("""\
            app:
              debug: true
            database:
              url: "postgresql://localhost/dev"
        """),
        encoding="utf-8",
    )

    return d
