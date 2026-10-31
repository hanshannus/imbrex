## Unreleased

### Feat

- add opt-in `secrets_ttl` cache for remote secrets, `imbrex.clear_secrets_cache()` and `Config.reload()`
- add `Config.with_overrides()`: a modified copy, safe for concurrent code and frozen configs
- add `${key}` / `${env:VAR:-default}` interpolation via `Config.interpolate()` (default in `load()`), with `ConfigInterpolationError`
- add `imbrex` CLI: `show`, `explain`, `validate`, `diff` (also `python -m imbrex`)
- add `imbrex.load()` / `load_config()`: files + `.env` + env vars + overrides in one call with a fixed precedence
- add `Config.from_dotenv()` and `coerce=True` for `from_env()` (bool, int, float, JSON)
- add attribute access (`cfg.database.url`) and `Config.explain(path)` for per-key provenance
- add `Config.to_dict(redact=True)` and mask sensitive-looking keys (`password`, `*_token`, `api_key`, `*_secret`, ...)
- `validate()` errors now list key paths without echoing input values; `ConfigValidationError.data` is redacted

### Fix

- `override()` could leave stale values behind when threads overlapped; overrides are now serialised by a lock
- derive `__version__` from package metadata (was stale at 0.1.1)

### Chore

- ship `py.typed` marker
- add test CI workflow (ruff, mypy, pytest on Python 3.11-3.13)

## 0.2.1 (2026-03-14)

### Refactor

- simplify conditional expressions and remove trailing whitespace in documentation

## 0.2.0 (2026-03-14)

### Feat

- add core configuration management classes and exception handling

## 0.1.1 (2026-03-14)

### Refactor

- clean up unused imports and improve code formatting in test files
- improve type hints and documentation in configuration modules
