# Provenance & Safe Output

Layered configuration raises one question again and again: *why does this key
have this value?* imbrex answers it, and keeps secrets out of the answer.

## `explain()`

```python
cfg = imbrex.load_config("config/", env="production", env_prefix="APP_")

print(cfg.explain("database.url"))
```

```text
database.url = 'postgresql://prod-db/app'
  from config/production.toml
  overrides config/defaults.toml: 'sqlite:///app.db'
```

`explain()` returns an [`Explanation`](../api/load.md) with:

| Attribute | Meaning |
|---|---|
| `path` | The dot-path you asked about |
| `value` | The winning value |
| `source` | The layer that supplied it: a file path, `.env` path, `<env prefix='APP_'>`, `<dict:0>`, `<string:toml>` or `<secret:aws>` |
| `overridden` | `(source, value)` pairs from lower-priority layers, lowest first |

A key that is not in the config raises `KeyError`.

!!! note "List merges"

    With the `ADDITIVE` merge strategy, `explain()` reports the highest layer
    that defined the key, not the concatenated list.

## Attribute access

Read nested values as attributes:

```python
cfg.database.url          # same as cfg["database.url"]
cfg.database.pool_size
```

Real attributes and methods win over keys of the same name, so a key called
`get` or `data` is still reachable as `cfg["get"]`. A nested section comes
back as a frozen `Config`, so `cfg.database.explain("url")` works too.

## Keeping secrets out of logs

Values stored under sensitive-looking keys are masked: `password`, `passwd`,
`pwd`, `secret`, `token`, `api_key`, `private_key` and `credential`, matched
anywhere in the key name (`client_secret`, `API_TOKEN`).

```python
cfg.to_dict(redact=True)
# {'database': {'url': '...', 'password': '***'}, ...}

print(cfg.explain("database.password"))
# database.password = '***'
#   from config/defaults.toml
```

The same masking applies to `ConfigValidationError.data` and to
`explain()`. Masking works on key names only, so a secret stored under a
neutral key such as `dsn` is not detected.

## Readable validation errors

`validate()` reports the key path and the source that supplied the bad value.
It does **not** echo the value itself:

```text
Validation failed:
  port: Input should be a valid integer, unable to parse string as an integer (from config/defaults.toml)
  name: Field required
```

Missing keys have no source, because nothing supplied them. The original
Pydantic error is still available as `exc.cause`.
