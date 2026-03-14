# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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

