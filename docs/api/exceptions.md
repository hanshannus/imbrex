# Exceptions

**imbrex** uses a typed exception hierarchy rooted at `ImbrexError`.  All
exceptions can be caught with a single `except ImbrexError` or individually.

## Hierarchy

```mermaid
graph TD
    Exception --> ImbrexError
    ImbrexError --> UnsupportedFormatError
    ImbrexError --> ConfigFileNotFoundError
    ImbrexError --> ConfigParseError
    ImbrexError --> ConfigValidationError
    ImbrexError --> ConfigSecretDescriptorError
    ImbrexError --> SecretProviderError
    ImbrexError --> FrozenConfigError
    FileNotFoundError --> ConfigFileNotFoundError
    AttributeError --> FrozenConfigError
```

!!! tip "`ConfigFileNotFoundError` inherits from both `ImbrexError` and `FileNotFoundError`"

    This means you can catch it with either `except ImbrexError` or
    `except FileNotFoundError`, depending on your error-handling style.

!!! tip "`FrozenConfigError` inherits from both `ImbrexError` and `AttributeError`"

    This allows frozen configs to work naturally with `hasattr()` and
    `getattr()` patterns.  You can catch it with `except ImbrexError`,
    `except AttributeError`, or `except FrozenConfigError`.

## `ImbrexError`

::: imbrex.ImbrexError
    options:
      show_source: true

## `UnsupportedFormatError`

::: imbrex.UnsupportedFormatError
    options:
      show_source: true

## `ConfigFileNotFoundError`

::: imbrex.ConfigFileNotFoundError
    options:
      show_source: true

## `ConfigParseError`

::: imbrex.ConfigParseError
    options:
      show_source: true

## `ConfigValidationError`

::: imbrex.ConfigValidationError
    options:
      show_source: true

## `ConfigSecretDescriptorError`

::: imbrex.ConfigSecretDescriptorError
    options:
      show_source: true

## `SecretProviderError`

::: imbrex.SecretProviderError
    options:
      show_source: true

## `FrozenConfigError`

::: imbrex.FrozenConfigError
    options:
      show_source: true

