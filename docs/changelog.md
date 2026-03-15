# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## 0.3.0 — (2026-03-15)

### Added

- **Frozen / immutable configs** — `Config.freeze()`, `Config.unfreeze()`,
  and `Config.is_frozen` property to lock a Config instance against mutation.
- **`freeze=True` parameter** on all factory classmethods (`from_toml`,
  `from_yaml`, `from_json`, `from_file`, `from_dir`, `from_dict`,
  `from_string`, `from_env`, `merge`) to freeze at construction time.
- **`FrozenConfigError`** — new exception raised when mutating a frozen Config.
  Inherits from both `ImbrexError` and `AttributeError`.
- **`Config.get()` dot-path access** — traverse nested dicts and list indices
  with `cfg.get("database.pool_size")` or `cfg.get("items.0")`.
- **`Config.override()` context manager** — temporarily patch dot-path keys
  for testing, with automatic restoration on exit.
- **`Config.__getitem__`** — bracket access with `cfg["database.pool_size"]`.
- **`Config.__contains__`** — membership test with `"database.pool_size" in cfg`.

## 0.2.1 — (2026-03-14)

### Refactor

- simplify conditional expressions and remove trailing whitespace in documentation

## 0.2.0 — (2026-03-14)

### Feat

- add core configuration management classes and exception handling

## 0.1.1 — (2026-03-14)

### Refactor

- clean up unused imports and improve code formatting in test files
- improve type hints and documentation in configuration modules

## 0.1.0 — (2026-03-14)

### Added

- **`Config` class** — immutable configuration container with dict-like access.
- **File loaders** — `from_toml()`, `from_yaml()`, `from_json()`, `from_file()`.
- **Directory loader** — `from_dir()` with automatic hierarchical priority sorting.
- **Raw data loaders** — `from_dict()`, `from_string()`, `from_env()`.
- **`Config.merge()`** — merge multiple `Config` objects with strategy control.
- **`Config.validate()`** — Pydantic v2 schema validation.
- **`MergeStrategy` enum** — `REPLACE`, `ADDITIVE`, `TYPESAFE`.
- **Per-key merge overrides** via `key_strategies` parameter.
- **`DEFAULT_PRIORITY` table** — built-in tier ordering for config file stems.
- **`sort_paths()`** and **`priority_of()`** — priority inspection utilities.
- **Environment variable resolution** — `APP_ENV` / `ENV` / `ENVIRONMENT`.
- **Typed exception hierarchy** — `ImbrexError`, `ConfigFileNotFoundError`,
  `ConfigParseError`, `ConfigValidationError`, `UnsupportedFormatError`.
