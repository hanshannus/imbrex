# Installation

## Requirements

- **Python ≥ 3.11**
- Core dependencies (installed automatically):
    - [`PyYAML`](https://pypi.org/project/PyYAML/) ≥ 6.0
    - [`python-dotenv`](https://pypi.org/project/python-dotenv/) ≥ 1.0

## Install with pip

```bash
pip install imbrex
```

To include [Pydantic](https://docs.pydantic.dev/) v2 for schema validation:

```bash
pip install "imbrex[pydantic]"
```

Or install everything:

```bash
pip install "imbrex[full]"
```

## Install with uv

[`uv`](https://docs.astral.sh/uv/) is a fast Python package manager:

```bash
uv add imbrex
uv add "imbrex[pydantic]"   # include Pydantic v2
```

## Install from source

```bash
git clone https://github.com/hanshannus/imbrex.git
cd imbrex
pip install -e ".[full]"
```

## Verify the installation

```python
>>> import imbrex
>>> imbrex.__version__
'0.1.0'
>>> from imbrex import Config
>>> cfg = Config.from_dict({"hello": "world"})
>>> cfg["hello"]
'world'
```

## Optional dependencies

| Extra | Installs | Purpose |
|---|---|---|
| `pydantic` | `pydantic ≥ 2.0` | Schema validation via `cfg.validate(MyModel)` |
| `full` | All of the above | Everything in one command |

!!! tip "Pydantic is optional"

    **imbrex** works perfectly without Pydantic.  You can load, merge, and
    access configuration as plain dicts.  Pydantic is only needed when you
    call `Config.validate()` with a `BaseModel` subclass.
