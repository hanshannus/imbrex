# Contributing to imbrex

Thank you for considering contributing to **imbrex**! This document describes
the development workflow, tooling, and release process in detail.

---

## Table of contents

- [Prerequisites](#prerequisites)
- [Getting started](#getting-started)
- [Project structure](#project-structure)
- [uv — package & project manager](#uv--package--project-manager)
  - [Dependency groups](#dependency-groups)
  - [Adding dependencies](#adding-dependencies)
  - [Running commands](#running-commands)
  - [The lockfile](#the-lockfile)
- [Code quality](#code-quality)
  - [Ruff (lint & format)](#ruff-lint--format)
  - [Mypy (type checking)](#mypy-type-checking)
  - [Tests (pytest)](#tests-pytest)
- [prek — pre-commit hooks](#prek--pre-commit-hooks)
  - [Installing hooks](#installing-hooks)
  - [Running hooks manually](#running-hooks-manually)
  - [Hook inventory](#hook-inventory)
  - [Updating hook versions](#updating-hook-versions)
- [Commit conventions (Commitizen)](#commit-conventions-commitizen)
  - [Writing commits](#writing-commits)
  - [Interactive commit](#interactive-commit)
  - [Commit types](#commit-types)
  - [Breaking changes](#breaking-changes)
  - [Validation](#validation)
- [Documentation (MkDocs)](#documentation-mkdocs)
  - [Building docs locally](#building-docs-locally)
  - [Writing docs](#writing-docs)
  - [API reference](#api-reference)
- [Release process](#release-process)
  - [Overview](#overview)
  - [Step 1 — Ensure a clean main branch](#step-1--ensure-a-clean-main-branch)
  - [Step 2 — Bump version with Commitizen](#step-2--bump-version-with-commitizen)
  - [Step 3 — Build distributions with uv](#step-3--build-distributions-with-uv)
  - [Step 4 — Publish to PyPI with uv](#step-4--publish-to-pypi-with-uv)
  - [Step 5 — Push the release](#step-5--push-the-release)
  - [Pre-release versions](#pre-release-versions)
  - [Dry-run workflow](#dry-run-workflow)
  - [How version_provider = "uv" works](#how-version_provider--uv-works)
  - [Release checklist](#release-checklist)

---

## Prerequisites

| Tool                              | Version | Purpose                               |
|-----------------------------------|---------|---------------------------------------|
| [Python](https://www.python.org/) | ≥ 3.11  | Runtime                               |
| [uv](https://docs.astral.sh/uv/)  | latest  | Package manager, venv, build, publish |
| [Git](https://git-scm.com/)       | ≥ 2.30  | Version control                       |

> **uv** manages the virtual environment, dependencies, lockfile, build, and
> publish — no need for `pip`, `setuptools`, `twine`, or `build` separately.

---

## Getting started

```bash
# 1. Clone the repository
git clone https://github.com/hanshannus/imbrex.git
cd imbrex

# 2. Install all dependencies (creates .venv automatically)
uv sync --all-groups

# 3. Install git hooks
uv run prek install

# 4. Verify everything works
uv run pytest
uv run ruff check src/
uv run mypy src/
```

After step 2, **uv** has created a `.venv/` in the project root with every
dependency from `dev`, `docs`, and the package itself installed in editable
mode.  Every command below is run via `uv run` so it automatically uses this
environment.

---

## Project structure

```text
imbrex/
├── src/imbrex/           # Package source code
│   ├── __init__.py
│   ├── _config.py        # Config class
│   ├── _exceptions.py    # Exception hierarchy
│   ├── _merge.py         # Merge strategies
│   ├── _parsers.py       # TOML / YAML / JSON parsers
│   └── _priority.py      # Priority table & sorting
├── tests/                # Test suite
├── docs/                 # MkDocs source files
├── pyproject.toml        # Project metadata, dependencies, tool config
├── uv.lock               # Locked dependency graph
├── cz.toml               # Commitizen configuration
├── prek.toml             # Pre-commit hook configuration
├── ruff.toml             # Ruff linter / formatter config
├── ruff_defaults.toml    # Base Ruff rule set
├── mkdocs.yml            # Documentation site config
└── CONTRIBUTING.md       # ← you are here
```

---

## uv — package & project manager

[uv](https://docs.astral.sh/uv/) is the single tool used for virtual
environment management, dependency resolution, locking, building, and
publishing.

### Dependency groups

Dependencies are organised into groups in `pyproject.toml`:

| Group        | Section                           | Contents                                              |
|--------------|-----------------------------------|-------------------------------------------------------|
| **Runtime**  | `[project] dependencies`          | `PyYAML`, `python-dotenv`                             |
| **Optional** | `[project.optional-dependencies]` | `pydantic` (via `imbrex[pydantic]` or `imbrex[full]`) |
| **Dev**      | `[dependency-groups] dev`         | `pytest`, `ruff`, `mypy`, `commitizen`, `prek`, etc.  |
| **Docs**     | `[dependency-groups] docs`        | `mkdocs-material`, `mkdocstrings[python]`             |

### Syncing dependencies

```bash
# Install runtime + dev dependencies (default)
uv sync

# Install everything, including docs group
uv sync --all-groups

# Install only a specific group
uv sync --group docs
```

### Adding dependencies

```bash
# Add a runtime dependency
uv add requests

# Add a dev-only dependency
uv add --group dev hypothesis

# Add a docs-only dependency
uv add --group docs mkdocs-git-revision-date-localized-plugin

# Add an optional dependency (e.g. under the "pydantic" extra)
# → edit pyproject.toml [project.optional-dependencies] manually
```

After any `uv add`, the `uv.lock` file is updated automatically.  **Always
commit `uv.lock`** so other contributors get reproducible installs.

### Running commands

`uv run` executes a command inside the project's virtual environment:

```bash
uv run pytest                    # run tests
uv run ruff check src/           # lint
uv run mypy src/                 # type-check
uv run mkdocs serve              # serve docs
uv run cz commit                 # interactive commit
uv run prek run --all-files      # run all hooks
```

You do **not** need to activate the virtual environment manually.

### The lockfile

`uv.lock` is a cross-platform, deterministic lockfile generated by uv.
It pins every transitive dependency to an exact version.

```bash
# Regenerate the lockfile (e.g. after editing pyproject.toml by hand)
uv lock

# Upgrade all dependencies to their latest compatible versions
uv lock --upgrade

# Upgrade a single package
uv lock --upgrade-package pydantic
```

> **Rule:** always commit `uv.lock` after any dependency change.

---

## Code quality

### Ruff (lint & format)

[Ruff](https://docs.astral.sh/ruff/) handles both linting and formatting.
Configuration lives in `ruff.toml` (which extends `ruff_defaults.toml`).

```bash
# Lint (with auto-fix)
uv run ruff check src/ tests/ --fix

# Format
uv run ruff format src/ tests/

# Check formatting without modifying files
uv run ruff format --check src/ tests/
```

Key settings:

- Line length: **88** characters (project) / **100** (pycodestyle max)
- Enabled rule sets: `E`, `F`, `W`, `I` (isort), `D` (docstrings), `UP` (pyupgrade), plus a comprehensive set from `ruff_defaults.toml`
- Ignored: `D1` (missing docstrings), `D203`/`D212` (docstring style conflicts)

### Mypy (type checking)

[Mypy](https://mypy-lang.org/) runs in strict mode on the `src/` directory:

```bash
uv run mypy src/
```

Configuration is in `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
files = ["src"]
```

### Tests (pytest)

[Pytest](https://docs.pytest.org/) is configured in `pyproject.toml`:

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=imbrex --cov-report=term-missing

# Run a specific test file
uv run pytest tests/test_merge.py

# Run a specific test class or method
uv run pytest tests/test_config.py::TestFromDir::test_env_development

# Run tests matching a keyword
uv run pytest -k "validation"
```

Test files are in `tests/` and are organised by module:

| File                 | Covers                                     |
|----------------------|--------------------------------------------|
| `test_exceptions.py` | Exception hierarchy and attributes         |
| `test_parsers.py`    | TOML / YAML / JSON parsing, file discovery |
| `test_merge.py`      | Merge strategies and per-key overrides     |
| `test_priority.py`   | Priority table, sorting, env filtering     |
| `test_config.py`     | `Config` loaders, dict access, merge, repr |
| `test_validation.py` | Pydantic schema validation                 |

---

## prek — pre-commit hooks

[prek](https://github.com/prek-org/prek) is a fast, Rust-based pre-commit
hook runner.  Configuration lives in `prek.toml`.

### Installing hooks

After cloning the repo, install the git hooks:

```bash
uv run prek install
```

This registers prek as the handler for the `pre-commit`, `commit-msg`, and
`pre-push` git hook stages.  From this point on, hooks run automatically on
every `git commit` and `git push`.

### Installing hook environments

To pre-download and install all hook environments (so the first commit
doesn't have a cold-start delay):

```bash
uv run prek install-hooks
```

### Running hooks manually

```bash
# Run all hooks on all files (useful before pushing)
uv run prek run --all-files

# Run all hooks on staged files only (what git commit does)
uv run prek run

# Run a specific hook
uv run prek run ruff
uv run prek run mypy
uv run prek run gitleaks
uv run prek run commitizen

# Run hooks on files changed since a ref
uv run prek run --from-ref main --to-ref HEAD
```

### Hook inventory

The following hooks are configured in `prek.toml`:

| Hook                      | Stage          | What it does                                          |
|---------------------------|----------------|-------------------------------------------------------|
| `trailing-whitespace`     | pre-commit     | Strips trailing whitespace                            |
| `end-of-file-fixer`       | pre-commit     | Ensures files end with a newline                      |
| `check-yaml`              | pre-commit     | Validates YAML syntax                                 |
| `check-toml`              | pre-commit     | Validates TOML syntax                                 |
| `check-added-large-files` | pre-commit     | Prevents accidental large file commits                |
| `check-merge-conflict`    | pre-commit     | Detects unresolved merge conflict markers             |
| `gitleaks`                | pre-commit     | Scans for hardcoded secrets and credentials           |
| `ruff`                    | pre-commit     | Lints Python with auto-fix (`--fix`)                  |
| `ruff-format`             | pre-commit     | Formats Python code                                   |
| `mypy`                    | pre-commit     | Type-checks `src/` in strict mode                     |
| `commitizen`              | **commit-msg** | Validates commit message against Conventional Commits |
| `commitizen-branch`       | **pre-push**   | Validates branch naming conventions                   |

### Updating hook versions

```bash
# Auto-update all hook revisions to their latest tags
uv run prek auto-update

# Then verify nothing broke
uv run prek run --all-files
```

### Uninstalling hooks

```bash
uv run prek uninstall
```

---

## Commit conventions (Commitizen)

This project uses [Commitizen](https://commitizen-tools.github.io/commitizen/)
with the **Conventional Commits** standard.  Configuration lives in `cz.toml`:

```toml
[tool.commitizen]
name = "cz_conventional_commits"
tag_format = "$version"
version_scheme = "semver2"
version_provider = "uv"
update_changelog_on_bump = true
```

### Writing commits

Every commit message **must** follow this format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Examples

```bash
# Simple feature
git commit -m "feat(config): add from_env() loader for environment variables"

# Bug fix
git commit -m "fix(parsers): handle empty YAML files returning None"

# Documentation
git commit -m "docs: add merge strategies guide"

# With body and footer
git commit -m "feat(merge): add TYPESAFE strategy

Raises TypeError when two values for the same key have incompatible types.
Recursive validation at every nesting level.

Closes #42"
```

### Interactive commit

Use `cz commit` for a guided, interactive experience:

```bash
uv run cz commit
```

This prompts you step-by-step:

1. **Type** — select from `feat`, `fix`, `docs`, etc.
2. **Scope** — optional component name (e.g. `config`, `parsers`, `merge`)
3. **Subject** — short imperative description
4. **Body** — longer explanation (optional)
5. **Breaking change** — describe if applicable (optional)
6. **Footer** — issue references (optional)

### Commit types

| Type       | SemVer effect  | When to use                                       |
|------------|----------------|---------------------------------------------------|
| `feat`     | **minor** bump | A new feature or public API addition              |
| `fix`      | **patch** bump | A bug fix                                         |
| `docs`     | —              | Documentation-only changes                        |
| `style`    | —              | Formatting, whitespace (no code change)           |
| `refactor` | —              | Code change that neither fixes nor adds a feature |
| `perf`     | —              | Performance improvement                           |
| `test`     | —              | Adding or correcting tests                        |
| `build`    | —              | Build system or dependency changes                |
| `ci`       | —              | CI/CD configuration changes                       |
| `chore`    | —              | Maintenance tasks                                 |

### Breaking changes

A breaking change triggers a **major** version bump.  Signal it in either
of two ways:

```bash
# Option 1: BREAKING CHANGE in footer
git commit -m "feat(config): rename from_env prefix parameter

BREAKING CHANGE: the 'prefix' parameter is now keyword-only"

# Option 2: exclamation mark after type
git commit -m "feat(config)!: rename from_env prefix parameter"
```

### Validation

The `commitizen` prek hook validates every commit message automatically at
the `commit-msg` stage.  If your message doesn't follow the convention, the
commit is rejected with a clear error.

You can also validate manually:

```bash
# Check the last commit message
uv run cz check --commit-msg-file .git/COMMIT_EDITMSG

# Check an arbitrary message
echo "feat: add thing" | uv run cz check
```

---

## Documentation (MkDocs)

Documentation is built with [MkDocs](https://www.mkdocs.org/) using the
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) theme
and [mkdocstrings](https://mkdocstrings.github.io/) for auto-generated API
reference from Python docstrings.

### Building docs locally

```bash
# Install docs dependencies (if not already synced)
uv sync --group docs

# Serve with live reload at http://127.0.0.1:8000
uv run mkdocs serve

# Build a static site into site/
uv run mkdocs build

# Build in strict mode (fail on warnings — use in CI)
uv run mkdocs build --strict
```

### Writing docs

Documentation source files live in `docs/`:

```text
docs/
├── index.md                       # Landing page
├── installation.md                # Install guide
├── changelog.md                   # Release notes
├── guide/
│   ├── getting-started.md         # Quick start
│   ├── loading.md                 # Loading configuration
│   ├── directory-priority.md      # Directory loading & priority
│   ├── merge-strategies.md        # REPLACE / ADDITIVE / TYPESAFE
│   ├── environment-variables.md   # from_env() and env detection
│   └── validation.md              # Pydantic validation
├── api/
│   ├── index.md                   # API overview
│   ├── config.md                  # Config class reference
│   ├── merge.md                   # MergeStrategy & deep_merge
│   ├── priority.md                # Priority table & functions
│   └── exceptions.md              # Exception hierarchy
└── examples/
    ├── cookbook.md                 # Copy-paste recipes
    └── patterns.md                # Real-world patterns
```

MkDocs features available:

- **Tabbed code blocks** — `=== "TOML"` / `=== "YAML"` / `=== "JSON"`
- **Admonitions** — `!!! tip`, `!!! warning`, `!!! danger`, `!!! note`
- **Mermaid diagrams** — fenced `mermaid` code blocks
- **Code copy buttons** — enabled globally
- **Dark / light mode** — auto-detected from system preference

### API reference

API docs are **auto-generated** from source docstrings using
`mkdocstrings`.  To document a class or function, add a directive in a
Markdown file:

```markdown
::: imbrex.Config
    options:
      show_source: true
      members:
        - from_toml
        - from_dir
        - validate
```

Docstrings should use **NumPy style** (`docstring_style: numpy` is
configured in `mkdocs.yml`):

```python
def my_function(path: Path, *, fmt: str = "toml") -> dict[str, Any]:
    """
    Short summary line.

    Longer description if needed.

    Parameters
    ----------
    path:
        Path to the config file.
    fmt:
        Format identifier.

    Returns
    -------
    dict[str, Any]
        The parsed configuration data.

    Raises
    ------
    ConfigParseError
        When the file cannot be parsed.
    """
```

---

## Release process

Releases use **Commitizen** to determine the next version from commit
history, bump version numbers, generate the changelog, and create a git
tag.  **uv** then builds and publishes the package to PyPI.

### Overview

```text
Conventional Commits  →  cz bump  →  uv build  →  uv publish  →  git push
         │                   │           │             │               │
    commit history     bumps version   sdist +      uploads to     pushes tag
    determines the     in pyproject,   wheel in     PyPI           to remote
    next version       updates         dist/
                       CHANGELOG.md,
                       commits & tags
```

### Step 1 — Ensure a clean main branch

```bash
git checkout main
git pull origin main
uv run pytest                        # all tests pass
uv run prek run --all-files          # all hooks pass
uv run mkdocs build --strict         # docs build cleanly
```

### Step 2 — Bump version with Commitizen

```bash
uv run cz bump
```

This single command:

1. **Analyses git history** since the last tag to determine the bump level:
   - `fix:` commits → **patch** bump (e.g. `0.1.0` → `0.1.1`)
   - `feat:` commits → **minor** bump (e.g. `0.1.0` → `0.2.0`)
   - `BREAKING CHANGE` → **major** bump (e.g. `0.1.0` → `1.0.0`)
2. **Updates the version** in `pyproject.toml` (`version_provider = "uv"`
   tells Commitizen to read/write the version from `[project] version`).
3. **Generates/updates `CHANGELOG.md`** (`update_changelog_on_bump = true`).
4. **Creates a commit** with the message `bump: version X.Y.Z → A.B.C`.
5. **Creates a git tag** matching `tag_format = "$version"` (e.g. `0.2.0`).

#### Forcing a specific bump level

```bash
# Force a minor bump regardless of commit types
uv run cz bump --increment MINOR

# Force a specific version
uv run cz bump 1.0.0
```

#### Pre-release versions

```bash
# Create an alpha pre-release
uv run cz bump --prerelease alpha
# e.g. 0.2.0 → 0.3.0a0

# Beta
uv run cz bump --prerelease beta
# e.g. 0.3.0a0 → 0.3.0b0

# Release candidate
uv run cz bump --prerelease rc
# e.g. 0.3.0b0 → 0.3.0rc0

# Final release (from any pre-release)
uv run cz bump
# e.g. 0.3.0rc0 → 0.3.0
```

### Step 3 — Build distributions with uv

```bash
uv build
```

This creates both a source distribution and a wheel in `dist/`:

```text
dist/
├── imbrex-0.2.0.tar.gz       # sdist
└── imbrex-0.2.0-py3-none-any.whl  # wheel
```

The build backend is `uv_build` (configured in `pyproject.toml`
`[build-system]`), so **no** `setuptools` or `build` is needed.

> **Tip:** add `--clear` to remove stale artifacts from previous builds:
>
> ```bash
> uv build --clear
> ```

### Step 4 — Publish to PyPI with uv

```bash
# Publish to PyPI
uv publish

# Publish to TestPyPI first (recommended for first-time releases)
uv publish --publish-url https://test.pypi.org/legacy/
```

Authentication options:

```bash
# Using an API token (recommended)
uv publish --token pypi-AgEI...

# Using environment variables
export UV_PUBLISH_TOKEN=pypi-AgEI...
uv publish

# Using username/password
uv publish --username __token__ --password pypi-AgEI...
```

> **Dry-run:** verify what would be uploaded without actually publishing:
>
> ```bash
> uv publish --dry-run
> ```

### Step 5 — Push the release

```bash
# Push the bump commit and the version tag
git push origin main --tags
```

### Dry-run workflow

To rehearse the full release without making any changes:

```bash
# 1. Preview what cz bump would do
uv run cz bump --dry-run

# 2. Preview the changelog
uv run cz changelog --dry-run

# 3. Build without publishing
uv build

# 4. Verify the package contents
tar -tzf dist/imbrex-*.tar.gz | head -20
unzip -l dist/imbrex-*.whl | head -20

# 5. Dry-run publish
uv publish --dry-run
```

### How `version_provider = "uv"` works

The `cz.toml` setting `version_provider = "uv"` tells Commitizen to:

- **Read** the current version from `pyproject.toml` → `[project] version`
  (using the same mechanism as `uv`).
- **Write** the bumped version back to `pyproject.toml` → `[project] version`.

This means `pyproject.toml` is the **single source of truth** for the
package version.  There is no separate `__version__` file to keep in sync
(the `__version__` in `__init__.py` should reference the same value or be
removed in favour of `importlib.metadata`).

The `tag_format = "$version"` setting means tags are plain version numbers
(e.g. `0.2.0`) without a `v` prefix.  The `version_scheme = "semver2"`
setting enforces [Semantic Versioning 2.0.0](https://semver.org/).

### Release checklist

```markdown
- [ ] All tests pass: `uv run pytest`
- [ ] All hooks pass: `uv run prek run --all-files`
- [ ] Docs build cleanly: `uv run mkdocs build --strict`
- [ ] On `main` branch with clean working tree
- [ ] Bump version: `uv run cz bump`
- [ ] Verify changelog: review `CHANGELOG.md`
- [ ] Build: `uv build --clear`
- [ ] Publish: `uv publish` (or `--dry-run` first)
- [ ] Push: `git push origin main --tags`
- [ ] Verify on PyPI: https://pypi.org/project/imbrex/
```

---

## Workflow summary

| Task | Command |
|---|---|
| Install everything | `uv sync --all-groups` |
| Install git hooks | `uv run prek install` |
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check src/ tests/ --fix` |
| Format | `uv run ruff format src/ tests/` |
| Type-check | `uv run mypy src/` |
| Run all hooks | `uv run prek run --all-files` |
| Interactive commit | `uv run cz commit` |
| Serve docs | `uv run mkdocs serve` |
| Build docs | `uv run mkdocs build --strict` |
| Preview release | `uv run cz bump --dry-run` |
| Release | `uv run cz bump && uv build --clear && uv publish` |
| Push release | `git push origin main --tags` |
