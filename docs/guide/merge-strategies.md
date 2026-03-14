# Merge Strategies

When multiple configuration sources define the same key, **strata** needs a
rule to decide the final value.  The `MergeStrategy` enum provides three
strategies.

## Overview

| Strategy | Lists | Scalars | Type mismatch |
|---|---|---|---|
| `REPLACE` *(default)* | Replaced entirely | Last value wins | Allowed |
| `ADDITIVE` | Concatenated | Last value wins | Allowed |
| `TYPESAFE` | Replaced entirely | Last value wins | **Raises `TypeError`** |

## REPLACE (default)

The higher-priority source **unconditionally wins** for every value type,
including lists:

```python
from strata import Config, MergeStrategy

cfg = Config.from_dict(
    {"hosts": ["a", "b"], "port": 80},
    {"hosts": ["c"],      "port": 443},
    merge_strategy=MergeStrategy.REPLACE,
)

print(cfg["hosts"])  # ["c"]     ← replaced, not merged
print(cfg["port"])   # 443       ← last value wins
```

This is the safest default — you always know exactly what you're getting from
each file.

## ADDITIVE

Lists are **concatenated** instead of replaced.  Scalars and dicts still
follow the normal merge rules:

```python
cfg = Config.from_dict(
    {"hosts": ["a", "b"], "port": 80},
    {"hosts": ["c"],      "port": 443},
    merge_strategy=MergeStrategy.ADDITIVE,
)

print(cfg["hosts"])  # ["a", "b", "c"]   ← concatenated
print(cfg["port"])   # 443               ← last value wins
```

This is ideal for settings like `allowed_hosts`, `plugins`, or `middleware`
where each layer should *add* to the list rather than replace it.

## TYPESAFE

Behaves like `REPLACE` but raises `TypeError` when two values for the same
key have **incompatible types**.  This catches configuration drift early:

```python
cfg = Config.from_dict(
    {"port": 8000},
    {"port": "not-a-number"},         # str vs int
    merge_strategy=MergeStrategy.TYPESAFE,
)
# TypeError: Type mismatch at 'port': existing=int, incoming=str
```

Type checking is recursive — nested dicts are validated at every level:

```python
Config.from_dict(
    {"database": {"pool_size": 5}},
    {"database": {"pool_size": "ten"}},
    merge_strategy=MergeStrategy.TYPESAFE,
)
# TypeError: Type mismatch at 'database.pool_size': existing=int, incoming=str
```

!!! tip "Use TYPESAFE in CI"

    Run your config loading with `TYPESAFE` in CI to catch accidental type
    changes between environment files before they hit production.

## Per-key strategy overrides

Apply a **different strategy to specific keys** while keeping the default for
everything else.  Keys are specified as dot-separated paths:

```python
cfg = Config.from_dir(
    "config/",
    extension="toml",
    env="production",
    merge_strategy=MergeStrategy.REPLACE,          # default
    key_strategies={
        "server.allowed_hosts": MergeStrategy.ADDITIVE,  # concatenate this list
    },
)
```

Given these files:

=== "defaults.toml"

    ```toml
    [server]
    allowed_hosts = ["localhost"]
    ```

=== "production.toml"

    ```toml
    [server]
    allowed_hosts = ["myapp.com", "www.myapp.com"]
    ```

Result:

```python
cfg["server"]["allowed_hosts"]
# ["localhost", "myapp.com", "www.myapp.com"]
```

Without the per-key override, the result would be
`["myapp.com", "www.myapp.com"]` (production replaces defaults).

## Using strategies with different loaders

The `merge_strategy` and `key_strategies` parameters are available on **every**
loader:

```python
# File loaders
Config.from_toml("a.toml", "b.toml", merge_strategy=MergeStrategy.ADDITIVE)
Config.from_yaml("a.yaml", "b.yaml", key_strategies={"list_key": MergeStrategy.ADDITIVE})

# Directory loader
Config.from_dir("config/", extension="toml", merge_strategy=MergeStrategy.TYPESAFE)

# Dict loader
Config.from_dict(dict1, dict2, merge_strategy=MergeStrategy.ADDITIVE)

# Merging Config objects
Config.merge(cfg1, cfg2, merge_strategy=MergeStrategy.ADDITIVE)
```

