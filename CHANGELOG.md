## 0.3.0 (2026-10-31)

### Feat

- add secrets_ttl cache and Config.reload()
- add ${key} and ${env:VAR:-default} interpolation
- add imbrex CLI with show, explain, validate and diff
- add load() front door, .env loading, attribute access and explain()
- redact secrets in errors and exports, add py.typed and test CI
- add support for frozen configuration with freeze/unfreeze methods and FrozenConfigError exception
- implement remote secrets loading from descriptor files for AWS/Azure/GCP
- add context manager for temporary configuration overrides and enhance get method for dot-path access

### Fix

- serialise override() across threads and add with_overrides()
- make Pydantic truly optional and name the source in validation errors

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
