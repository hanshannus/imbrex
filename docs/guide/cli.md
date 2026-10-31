# Command Line

The `imbrex` command answers the questions you otherwise answer with a
`print()` and a debugger: *what is the merged config, where did this value
come from, is it valid, and what changes between staging and production?*

```bash
imbrex show     [DIR]                   # print the merged config
imbrex explain  KEY [DIR]               # where did this value come from?
imbrex validate pkg.module:Model [DIR]  # check against a Pydantic model
imbrex diff     DIR ENV_A ENV_B         # compare two environments
```

`python -m imbrex ...` works as well.

!!! note "Validation needs Pydantic"

    `validate` loads your model, so it needs `imbrex[pydantic]` and your
    project importable from the current directory.

## Where the config comes from

Every command reads the same sources as [`imbrex.load()`](load.md), with the
same precedence: files, then `.env`, then environment variables.

| Option | Meaning |
|---|---|
| `DIR` | Config directory. Defaults to `./config` when it exists; otherwise files are skipped. |
| `--env NAME` | Environment tier (`production`...). Falls back to `APP_ENV`, `ENV`, `ENVIRONMENT`. |
| `--prefix APP_` | Prefix of the environment variables to read. Without it, real env vars are ignored. |
| `--dotenv PATH` / `--no-dotenv` | Dotenv file (default `.env`; a missing file is ignored). |
| `--extension toml\|yaml\|json` | Config format. Auto-detected when the directory has one format. |

## `show`

Prints the merged config as JSON (or `--format yaml`). Sensitive values are
masked; add `--reveal` to print them.

```console
$ imbrex show --env production --prefix APP_
{
  "database": {
    "url": "postgresql://prod-db/app",
    "pool_size": 20,
    "password": "***"
  },
  "debug": true
}
```

## `explain`

```console
$ imbrex explain database.url --env production
database.url = 'postgresql://prod-db/app'
  from config/production.toml
  overrides config/defaults.toml: 'sqlite:///app.db'
```

Exits with status 1 when the key does not exist. See
[Provenance](provenance.md) for what the output means.

## `validate`

```console
$ imbrex validate myapp.settings:Settings --env production
error: Validation failed:
  api_token: Field required
```

Prints `OK` and exits 0 when the config is valid, otherwise lists the failing
key paths (and the file that supplied each bad value) and exits 1. That makes
it a one-line CI or deploy gate:

```bash
imbrex validate myapp.settings:Settings config/ --env production
```

## `diff`

Shows what changes when you move from one environment to another:

```console
$ imbrex diff config staging production
--- staging
+++ production
+ cache.ttl = 60
~ database.url: 'postgresql://stg/app' -> 'postgresql://prod-db/app'
```

`+` is only in the second environment, `-` only in the first, `~` differs.
Sensitive keys are listed as changed without their values.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success (`diff` returns 0 even when there are differences) |
| `1` | Config error: missing directory or key, parse error, invalid config, bad schema path |
| `2` | Usage error (unknown command or option) |
