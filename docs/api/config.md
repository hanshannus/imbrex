# `Config`

The central class in **strata** — an immutable, merged configuration container.

All loading is done through classmethods; the resulting `Config` object provides
dict-like read access, source tracking, and Pydantic validation.

## Class reference

::: strata.Config
    options:
      show_source: true
      members:
        - __init__
        - data
        - sources
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
        - __getitem__
        - __contains__
        - __len__
        - __iter__
        - to_dict
        - __repr__
        - __eq__

