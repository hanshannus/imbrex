# Interpolation

Values can refer to other keys and to environment variables, so you say each
thing once:

```toml
[database]
host = "db.internal"
port = 5432
url  = "postgresql://${database.host}:${database.port}/app"
user = "${env:DB_USER:-app}"
```

```python
cfg = imbrex.load_config("config/")     # resolves ${...} after merging
cfg["database.url"]                      # 'postgresql://db.internal:5432/app'
```

## Syntax

| Write | Meaning |
|---|---|
| `${database.host}` | Another key, by dot-path |
| `${env:HOME}` | An environment variable |
| `${env:PORT:-8080}` | The variable, or `8080` when it is not set |
| `${database.host:-localhost}` | The key, or `localhost` when it is missing |
| `$${` | A literal `${` |

- **References are resolved after merging.** A reference sees the final
  value, so an override in `production.toml` flows into every value that
  uses it.
- **A lone reference keeps its type.** `workers = "${defaults.workers}"`
  becomes the integer, not a string. Inside longer text the value is
  converted to a string. Values from `env:` are always strings.
- **References can chain** (`a → b → c`). Circular references and missing
  keys or variables raise `ConfigInterpolationError`, naming the key that
  holds the reference:

```text
Cannot resolve ${database.hots} in 'database.url': key 'database.hots' not found
Cannot resolve ${b} in 'a': circular reference: b -> a -> b
```

## Where it runs

| API | Interpolates? |
|---|---|
| [`imbrex.load()` / `load_config()`](load.md) | Yes. Disable with `interpolate=False`. |
| `Config.from_dir()`, `from_toml()`, `merge()`, ... | No: call `cfg.interpolate()` yourself. |
| `imbrex show / explain / validate / diff` | Yes (they use `load_config`). |

`cfg.interpolate(env=...)` returns a new `Config` and accepts a mapping to use
instead of `os.environ`, which is handy in tests. The original is untouched.

[`explain()`](provenance.md) reports resolved values. A lower-priority value
that was overridden and cannot be resolved (for example it names an unset
variable) is shown as written.

!!! warning "Secrets containing `${`"

    Interpolation also runs on values fetched from remote secret providers.
    A secret that literally contains `${` must write it as `$${`, or load the
    config with `interpolate=False`.
