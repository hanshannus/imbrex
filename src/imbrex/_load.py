"""The one-call front door: files + ``.env`` + environment → typed settings."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, overload

from imbrex._config import Config
from imbrex._exceptions import ConfigFileNotFoundError, ImbrexError
from imbrex._parsers import SUPPORTED_FORMATS

if TYPE_CHECKING:
    from pydantic import BaseModel

T = TypeVar("T", bound="BaseModel")

_EXT_FOR = {".toml": "toml", ".yaml": "yaml", ".yml": "yaml", ".json": "json"}


def _detect_extension(directory: Path) -> str:
    found = sorted({
        _EXT_FOR[p.suffix.lower()]
        for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in _EXT_FOR
    })
    if len(found) > 1:
        raise ImbrexError(
            f"{directory} mixes config formats ({', '.join(found)}); "
            "pass extension=... to choose one "
            f"(supported: {', '.join(SUPPORTED_FORMATS)})."
        )
    return found[0] if found else "toml"


def load_config(
    directory: str | Path | None = None,
    *,
    env: str | None = None,
    env_prefix: str = "",
    dotenv: str | Path | None = ".env",
    extension: str | None = None,
    overrides: dict[str, Any] | None = None,
    interpolate: bool = True,
) -> Config:
    """
    Build a :class:`Config` from every standard source, in a fixed order.

    Precedence, lowest to highest::

        files in *directory* (by environment tier)
          < *dotenv* file < real environment variables < *overrides*

    Parameters
    ----------
    directory: str | Path | None
        Config directory.  ``None`` skips files entirely.
    env: str | None
        Environment tier (``"production"`` ...).  Defaults to ``APP_ENV`` /
        ``ENV`` / ``ENVIRONMENT``.
    env_prefix: str
        Prefix of the environment variables to read
        (``APP_DATABASE__URL`` → ``database.url``).  Real env vars are only
        read when a prefix is given; the dotenv file is read in full.
    dotenv: str | Path | None
        Dotenv file; a missing file is ignored.  ``None`` disables it.
    extension: str | None
        ``"toml"``, ``"yaml"`` or ``"json"``.  Auto-detected when the
        directory holds a single format.
    overrides: dict | None
        Highest-priority values, e.g. from CLI flags.
    interpolate: bool
        Resolve ``${key}`` / ``${env:VAR}`` references after merging
        (see :meth:`Config.interpolate`).  Default ``True``.

    """
    layers: list[Config] = []

    if directory is not None:
        d = Path(directory)
        if not d.is_dir():
            raise ConfigFileNotFoundError(d)
        layers.append(
            Config.from_dir(d, extension=extension or _detect_extension(d), env=env)
        )
    if dotenv is not None:
        layers.append(
            Config.from_dotenv(dotenv, env_prefix, coerce=True, required=False)
        )
    if env_prefix:  # never merge the whole of os.environ
        layers.append(Config.from_env(env_prefix, coerce=True))
    if overrides:
        layers.append(Config.from_dict(overrides))

    cfg = Config.merge(*layers)
    return cfg.interpolate() if interpolate else cfg


@overload
def load(
    schema: type[T],
    directory: str | Path | None = ...,
    **kwargs: Any,
) -> T: ...
@overload
def load(
    schema: None,
    directory: str | Path | None = ...,
    **kwargs: Any,
) -> Config: ...
def load(
    schema: type[T] | None,
    directory: str | Path | None = None,
    **kwargs: Any,
) -> T | Config:
    """
    Load every config source and return a validated *schema* instance.

    See :func:`load_config` for the accepted keyword arguments and the
    precedence order.  Pass ``schema=None`` to get the raw :class:`Config`.
    """
    cfg = load_config(directory, **kwargs)
    return cfg if schema is None else cfg.validate(schema)
