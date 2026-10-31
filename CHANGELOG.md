## Unreleased

### Feat

- add `Config.to_dict(redact=True)` and mask sensitive-looking keys (`password`, `*_token`, `api_key`, `*_secret`, ...)
- `validate()` errors now list key paths without echoing input values; `ConfigValidationError.data` is redacted

### Fix

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
