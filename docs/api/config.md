# `Config`

The central class in **imbrex** — a merged configuration container with
optional immutability via `freeze()`.

All loading is done through classmethods; the resulting `Config` object provides
dict-like read access, dot-path traversal, source tracking, temporary overrides,
and Pydantic validation.

## Class reference

::: imbrex.Config
    options:
      show_source: true
      members:
        - __init__
        - data
        - sources
        - is_frozen
        - from_toml
        - from_yaml
        - from_json
        - from_file
        - from_dir
        - from_dict
        - from_string
        - from_env
        - merge
        - validate
        - get
        - override
        - freeze
        - unfreeze
        - __getitem__
        - __contains__
        - __len__
        - __iter__
        - to_dict
        - __repr__
        - __eq__
