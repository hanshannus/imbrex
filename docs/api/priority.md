# Priority

Built-in priority table and path-sorting utilities for hierarchical
configuration ordering.

## `DEFAULT_PRIORITY`

::: strata.DEFAULT_PRIORITY
    options:
      show_source: false

The built-in mapping of file stem → integer priority:

| Stem | Priority |
|---|---:|
| `defaults` / `default` | 100 |
| `base` / `common` / `shared` | 200 |
| `development` / `dev` | 300 |
| `test` / `testing` / `staging` | 400 |
| `production` / `prod` | 500 |
| `local` | 600 |
| `secrets` / `secret` | 700 |

Unknown stems receive priority **0** (loaded first, overridden by everything).

## `sort_paths()`

::: strata._priority.sort_paths
    options:
      show_source: true

## `priority_of()`

::: strata._priority.priority_of
    options:
      show_source: true

