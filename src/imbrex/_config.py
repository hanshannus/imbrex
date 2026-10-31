"""
imbrex.Config — hierarchical configuration loader and validator.

The :class:`Config` object is an immutable wrapper around a merged ``dict``.
All loading is done through classmethods; the constructor is intentionally
private so the public API stays ergonomic::

    from imbrex import Config

    # ── Single file ────────────────────────────────────────────────────
    cfg = Config.from_toml("settings.toml")
    cfg = Config.from_yaml("settings.yaml")
    cfg = Config.from_json("settings.json")

    # ── Multiple files (merged in the order given) ─────────────────────
    cfg = Config.from_toml("defaults.toml", "production.toml")

    # ── Entire directory (auto-sorted by priority tier) ────────────────
    cfg = Config.from_dir("config/", extension="toml")
    cfg = Config.from_dir("config/", extension="toml", env="production")

    # ── Raw data ───────────────────────────────────────────────────────
    cfg = Config.from_dict({"database": {"url": "sqlite:///app.db"}})
    cfg = Config.from_string(toml_text, fmt="toml")

    # ── Validate and get a typed settings object ───────────────────────
    settings = cfg.validate(AppSettings)  # Pydantic BaseModel subclass
    print(settings.database.url)

    # ── Merge multiple Config objects ──────────────────────────────────
    merged = Config.merge(defaults_cfg, env_cfg, local_cfg)
"""

from __future__ import annotations

import copy
import os
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from dotenv import dotenv_values

from imbrex._env import nest_env
from imbrex._exceptions import (
    ConfigFileNotFoundError,
    ConfigValidationError,
    FrozenConfigError,
    ImbrexError,
    UnsupportedFormatError,
)
from imbrex._explain import Explanation, build_explanation
from imbrex._interpolate import Resolver
from imbrex._merge import MergeStrategy, deep_merge
from imbrex._parsers import (
    SUPPORTED_FORMATS,
    parse_file,
    parse_string,
)
from imbrex._priority import DEFAULT_PRIORITY, sort_paths
from imbrex._redact import redact as _redact
from imbrex._secrets_cache import clear_secrets_cache
from imbrex._utils import _MISSING, _get_path, _set_path, is_secret_descriptor

if TYPE_CHECKING:
    from pydantic import BaseModel

_OVERRIDE_LOCK = threading.RLock()

T = TypeVar("T", bound="BaseModel")


class Config:
    __slots__ = ("_data", "_sources", "_frozen", "_layers", "_reload")

    _data: dict[str, Any]
    _sources: list[str]
    _frozen: bool
    _layers: list[tuple[str, dict[str, Any]]]
    _reload: Callable[[bool], Config] | None

    def __init__(
        self,
        data: dict[str, Any],
        sources: list[str],
        *,
        freeze: bool = False,
        layers: list[tuple[str, dict[str, Any]]] | None = None,
    ) -> None:
        """
        Immutable, merged configuration container.

        Attributes
        ----------
        data:
            The raw merged dict.  Treat this as read-only; use :meth:`validate`
            to get a typed, attribute-accessible settings object.
        sources:
            Ordered list of source descriptors (file paths or tags like
            ``"<dict:0>"``) that contributed to this config, from lowest to
            highest priority.
        freeze:
            When *True* the instance is immediately frozen; any subsequent
            mutation attempt (``override``, direct ``_data`` replacement)
            raises :class:`FrozenConfigError`.

        """
        # Deliberately no public __init__ — use class methods.
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_sources", sources)
        object.__setattr__(self, "_frozen", freeze)
        object.__setattr__(self, "_layers", layers or [])
        object.__setattr__(self, "_reload", None)

    # ------------------------------------------------------------------
    # Freeze / unfreeze
    # ------------------------------------------------------------------

    def _check_frozen(self, operation: str = "mutate") -> None:
        """Raise if the instance is frozen."""
        if self._frozen:
            raise FrozenConfigError(operation)

    @property
    def is_frozen(self) -> bool:
        """Return *True* if the config is frozen."""
        return self._frozen

    def freeze(self) -> Config:
        """
        Lock the config so any mutation raises :class:`FrozenConfigError`.

        Returns *self* so you can chain: ``cfg = Config.from_dict(...).freeze()``
        """
        object.__setattr__(self, "_frozen", True)
        return self

    def unfreeze(self) -> Config:
        """
        Unlock a previously frozen config.

        Returns *self* for chaining.
        """
        object.__setattr__(self, "_frozen", False)
        return self

    def __setattr__(self, name: str, value: Any) -> None:
        # Guard _data and _sources against external mutation when frozen.
        if name in ("_data", "_sources") and self._frozen:
            raise FrozenConfigError(f"set {name}")
        object.__setattr__(self, name, value)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def data(self) -> dict[str, Any]:
        """The raw merged configuration dict (read-only view)."""
        return self._data

    @property
    def sources(self) -> list[str]:
        """Ordered list of source labels (lowest to highest priority)."""
        return self._sources

    # ------------------------------------------------------------------
    # Classmethods — file-based loaders
    # ------------------------------------------------------------------

    @classmethod
    def from_toml(
        cls,
        *files: str | Path,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        key_strategies: dict[str, MergeStrategy] | None = None,
        freeze: bool = False,
    ) -> Config:
        """
        Load one or more TOML files, merging in the order given.

        The *last* file has the highest priority (its values override all
        previous ones).

        Parameters
        ----------
        *files:
            One or more paths to ``.toml`` files.
        merge_strategy:
            Default merge strategy (REPLACE / ADDITIVE / TYPESAFE).
        key_strategies:
            Per-key overrides keyed by dot-separated paths.
        freeze:
            Lock the returned Config against mutation.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        return cls._load_files(
            [Path(f) for f in files],
            merge_strategy=merge_strategy,
            key_strategies=key_strategies,
            freeze=freeze,
        )

    @classmethod
    def from_yaml(
        cls,
        *files: str | Path,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        key_strategies: dict[str, MergeStrategy] | None = None,
        freeze: bool = False,
    ) -> Config:
        """
        Load one or more YAML files, merging in the order given.

        Parameters
        ----------
        *files:
            One or more paths to ``.yaml`` files.
        merge_strategy:
            Default merge strategy (REPLACE / ADDITIVE / TYPESAFE).
        key_strategies:
            Per-key overrides keyed by dot-separated paths.
        freeze:
            Lock the returned Config against mutation.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        return cls._load_files(
            [Path(f) for f in files],
            merge_strategy=merge_strategy,
            key_strategies=key_strategies,
            freeze=freeze,
        )

    @classmethod
    def from_json(
        cls,
        *files: str | Path,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        key_strategies: dict[str, MergeStrategy] | None = None,
        freeze: bool = False,
    ) -> Config:
        """
        Load one or more JSON files, merging in the order given.

        Parameters
        ----------
        *files:
            One or more paths to ``.json`` files.
        merge_strategy:
            Default merge strategy (REPLACE / ADDITIVE / TYPESAFE).
        key_strategies:
            Per-key overrides keyed by dot-separated paths.
        freeze:
            Lock the returned Config against mutation.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        return cls._load_files(
            [Path(f) for f in files],
            merge_strategy=merge_strategy,
            key_strategies=key_strategies,
            freeze=freeze,
        )

    @classmethod
    def from_file(
        cls,
        *files: str | Path,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        key_strategies: dict[str, MergeStrategy] | None = None,
        freeze: bool = False,
    ) -> Config:
        """
        Load one or more files of *any* supported format.

        Parameters
        ----------
        *files:
            One or more paths to ``.json`` files.
        merge_strategy:
            Default merge strategy (REPLACE / ADDITIVE / TYPESAFE).
        key_strategies:
            Per-key overrides keyed by dot-separated paths.
        freeze:
            Lock the returned Config against mutation.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        return cls._load_files(
            [Path(f) for f in files],
            merge_strategy=merge_strategy,
            key_strategies=key_strategies,
            freeze=freeze,
        )

    # ------------------------------------------------------------------
    # Classmethods — directory loader
    # ------------------------------------------------------------------

    @classmethod
    def from_dir(
        cls,
        directory: str | Path,
        *,
        extension: str = "toml",
        env: str | None = None,
        order: list[str] | None = None,
        recursive: bool = False,
        priority_table: dict[str, int] | None = None,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        key_strategies: dict[str, MergeStrategy] | None = None,
        freeze: bool = False,
        secrets_ttl: float | None = None,
    ) -> Config:
        """
        Discover and load all config files in *directory*.

        Sorted hierarchically so that higher-priority files override lower ones.

        Parameters
        ----------
        directory: str | Path
            Path to the config directory.
        extension: str (default: "toml")
            File extension to scan for (e.g. ``"toml"``, ``"yaml"``).
        env: str (default: "development")
            Active environment name (e.g. ``"production"``).  Files whose
            priority tier is *above* this environment are excluded so loading
            with ``env="development"`` never silently applies production
            overrides.  Auto-detected from ``APP_ENV`` / ``ENV`` /
            ``ENVIRONMENT`` when *None*.
        order: list[str] | None
            Explicit list of file stems in load order, e.g.
            ``["defaults", "development", "production"]``.  When given,
            *only* these stems are loaded (in exactly this order) and the
            automatic priority sort is bypassed.
        recursive: bool (default: False)
            Descend into sub-directories.
        priority_table: dict[str, int] | None
            Custom priority entries merged on top of the built-in table.
        merge_strategy: MergeStrategy (default: "REPLACE")
            Default merge strategy.
        key_strategies: dict[str, MergeStrategy] | None
            Per-key merge strategy overrides.
        secrets_ttl: float | None (default: None)
            Reuse fetched remote secrets for this many seconds.  ``None`` (or
            ``0``) fetches on every call.  See :func:`imbrex.clear_secrets_cache`.
        freeze: bool (default: False)
            Lock the returned Config against mutation.

        Default priority tiers
        ----------------------
        ============= ========
        Stem(s)       Priority
        ============= ========
        defaults      100
        base/common   200
        dev           300
        test/staging  400
        production    500
        local         600
        secrets       700
        ============= ========

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """

        def attach(cfg: Config) -> Config:
            def rebuild(refresh_secrets: bool) -> Config:
                if refresh_secrets:
                    clear_secrets_cache()
                return cls.from_dir(
                    directory,
                    extension=extension,
                    env=env,
                    order=order,
                    recursive=recursive,
                    priority_table=priority_table,
                    merge_strategy=merge_strategy,
                    key_strategies=key_strategies,
                    freeze=freeze,
                    secrets_ttl=secrets_ttl,
                )

            return cfg._with_reload(rebuild)

        d = Path(directory)
        if not d.exists():
            raise ConfigFileNotFoundError(d)
        if not d.is_dir():
            raise NotADirectoryError(f"Expected a directory: {d}")

        ext = extension if extension.startswith(".") else f".{extension}"
        glob = "**/*" if recursive else "*"
        all_paths = sorted(
            p
            for p in d.glob(glob)
            if p.is_file() and p.suffix.lower() in {".toml", ".yaml", ".yml", ".json"}
        )

        descriptor_paths = [p for p in all_paths if is_secret_descriptor(p)]
        file_paths = [
            p
            for p in all_paths
            if p.suffix.lower() == ext.lower() and not is_secret_descriptor(p)
        ]

        if order is not None:
            # Explicit stem ordering — ignore auto-priority
            stem_to_path = {p.stem.lower(): p for p in file_paths}
            sorted_paths: list[Path] = []
            for stem in order:
                p = stem_to_path.get(stem.lower())
                if p is not None:
                    sorted_paths.append(p)
        else:
            resolved_env = (
                env
                or os.environ.get("APP_ENV")
                or os.environ.get("ENV")
                or os.environ.get("ENVIRONMENT")
            )
            sorted_paths = sort_paths(
                file_paths,
                env=resolved_env,
                priority_table={**DEFAULT_PRIORITY, **(priority_table or {})},
            )

        base_config = cls._load_files(
            sorted_paths,
            merge_strategy=merge_strategy,
            key_strategies=key_strategies,
            freeze=freeze,
        )

        if not descriptor_paths:
            return attach(base_config)

        try:
            from imbrex._secrets import load_remote_secrets
        except ImportError as exc:  # pragma: no cover - needs a bare install
            raise ImportError(
                "Secret descriptor files need Pydantic: "
                "pip install 'imbrex[pydantic]' (plus a provider extra such as "
                "'imbrex[aws]')."
            ) from exc

        secret_data, secret_sources = load_remote_secrets(
            descriptor_paths,
            merge_strategy=merge_strategy,
            key_strategies=key_strategies,
            cache_ttl=secrets_ttl,
        )
        if not secret_data:
            return attach(base_config)

        merged = deep_merge(
            base_config.data,
            secret_data,
            strategy=merge_strategy,
            key_strategies=key_strategies,
        )
        return attach(
            cls(
                merged,
                [*base_config.sources, *secret_sources],
                freeze=freeze,
                layers=[
                    *base_config._layers,
                    (", ".join(secret_sources), secret_data),
                ],
            )
        )

    # ------------------------------------------------------------------
    # Classmethods — raw-data loaders
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(
        cls,
        *dicts: dict[str, Any],
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        key_strategies: dict[str, MergeStrategy] | None = None,
        freeze: bool = False,
    ) -> Config:
        """
        Build a :class:`Config` from one or more plain dicts.

        Dicts are merged left-to-right; the *last* dict wins.

        Parameters
        ----------
        *dicts: dict[str, Any]
            One or more dicts to merge in order.
        merge_strategy: MergeStrategy (default: "REPLACE")
            Default merge strategy for every key.
        key_strategies: dict[str, MergeStrategy] | None
            Per-key overrides keyed by dot-separated paths, e.g.
            ``{"server.allowed_hosts": MergeStrategy.ADDITIVE}``.
        freeze: bool (default: False)
            Lock the returned Config against mutation.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        sources = [f"<dict:{i}>" for i in range(len(dicts))]
        merged = deep_merge(
            *dicts, strategy=merge_strategy, key_strategies=key_strategies
        )
        return cls(merged, sources, freeze=freeze, layers=list(zip(sources, dicts)))

    @classmethod
    def from_string(
        cls,
        content: str,
        *,
        fmt: str,
        freeze: bool = False,
    ) -> Config:
        """
        Parse a raw *content* string.

        Parameters
        ----------
        content: str
            Raw config text.
        fmt: str
            Format identifier: ``"toml"``, ``"yaml"``, or ``"json"``.
        freeze: bool (default: False)
            Lock the returned Config against mutation.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        fmt = fmt.lower().strip(".")
        if fmt not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(fmt, SUPPORTED_FORMATS)
        data = parse_string(content, fmt=fmt)
        label = f"<string:{fmt}>"
        return cls(data, [label], freeze=freeze, layers=[(label, data)])

    @classmethod
    def from_env(
        cls,
        prefix: str = "",
        *,
        separator: str = "__",
        coerce: bool = False,
        freeze: bool = False,
    ) -> Config:
        """
        Build a :class:`Config` from environment variables.

        Variable names are lower-cased and *separator* (default ``__``) is
        converted to nested dict keys::

            APP_DATABASE__URL=postgres://host/db
            → {"database": {"url": "postgres://host/db"}}

        Parameters
        ----------
        prefix: str (default: "")
            Only variables beginning with *prefix* are included.
            The prefix itself is stripped before key conversion.
        separator: str (default: "__")
            Nesting separator in variable names.
        coerce: bool (default: False)
            Convert ``true``/``false``, integers, floats and JSON lists or
            objects to Python values instead of leaving strings.
        freeze: bool (default: False)
            Lock the returned Config against mutation.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        data = nest_env(os.environ, prefix, separator=separator, coerce=coerce)
        label = f"<env prefix={prefix!r}>"
        return cls(data, [label], freeze=freeze, layers=[(label, data)])

    @classmethod
    def from_dotenv(
        cls,
        path: str | Path = ".env",
        prefix: str = "",
        *,
        separator: str = "__",
        coerce: bool = False,
        required: bool = True,
        freeze: bool = False,
    ) -> Config:
        """
        Build a :class:`Config` from a ``.env`` file.

        Uses the same naming rules as :meth:`from_env` (``APP_DB__URL`` →
        ``db.url``).  The file is only read: ``os.environ`` is not modified.

        Parameters
        ----------
        path: str | Path (default: ".env")
            The dotenv file.
        prefix: str (default: "")
            Only variables beginning with *prefix* are included.
        separator: str (default: "__")
            Nesting separator in variable names.
        coerce: bool (default: False)
            See :meth:`from_env`.
        required: bool (default: True)
            When ``False`` a missing file yields an empty Config instead of
            raising :class:`ConfigFileNotFoundError`.
        freeze: bool (default: False)
            Lock the returned Config against mutation.

        """
        p = Path(path)
        if not p.is_file():
            if required:
                raise ConfigFileNotFoundError(p)
            return cls({}, [], freeze=freeze)
        data = nest_env(dotenv_values(p), prefix, separator=separator, coerce=coerce)
        return cls(data, [str(p)], freeze=freeze, layers=[(str(p), data)])

    # ------------------------------------------------------------------
    # Classmethod — merge existing Config objects
    # ------------------------------------------------------------------

    @classmethod
    def merge(
        cls,
        *configs: Config,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        key_strategies: dict[str, MergeStrategy] | None = None,
        freeze: bool = False,
    ) -> Config:
        """
        Merge multiple :class:`Config` objects into one.

        The *last* config has the highest priority.

        Parameters
        ----------
        *configs: :class:`Config`
            One or more Config instances to merge in order.
        merge_strategy: :class:`MergeStrategy`
            Default merge strategy for every key.
        key_strategies: dict[str, :class:`MergeStrategy`]
            Per-key overrides keyed by dot-separated paths, e.g.
            ``{"server.allowed_hosts": MergeStrategy.ADDITIVE}``.
        freeze: bool (default: False)
            Lock the returned Config against mutation.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        dicts = [c._data for c in configs]
        sources = [src for c in configs for src in c._sources]
        layers = [layer for c in configs for layer in c._layers]
        merged = deep_merge(
            *dicts, strategy=merge_strategy, key_strategies=key_strategies
        )
        return cls(merged, sources, freeze=freeze, layers=layers)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, schema: type[T]) -> T:
        """
        Validate the merged config against *schema*.

        *schema* must be a **Pydantic v2** ``BaseModel`` subclass.  If you
        pass a plain dataclass or any other callable that accepts ``**kwargs``
        it will be invoked without Pydantic's validation layer.

        Parameters
        ----------
        schema: type[T]
            A Pydantic ``BaseModel`` subclass (recommended) or any callable
            that accepts ``**kwargs`` and returns a settings object.

        Returns
        -------
        T
            An instance of *schema* populated with the validated config data.

        Raises
        ------
        ConfigValidationError
            When Pydantic reports one or more field errors.
        ImportError
            When Pydantic is not installed and the schema is a
            ``BaseModel`` subclass.

        Example
        -------
        ::

            from pydantic import BaseModel


            class DBConfig(BaseModel):
                url: str
                pool_size: int = 5


            class AppSettings(BaseModel):
                debug: bool = False
                database: DBConfig


            settings = cfg.validate(AppSettings)
            print(settings.database.url)

        """
        try:
            from pydantic import BaseModel as _BaseModel
            from pydantic import ValidationError
        except ImportError:  # Pydantic is optional: plain callables still work
            _BaseModel = None  # type: ignore[assignment,misc]

        if (
            _BaseModel is not None
            and isinstance(schema, type)
            and issubclass(schema, _BaseModel)
        ):
            try:
                return schema.model_validate(self._data)
            except ValidationError as exc:
                lines = []
                for e in exc.errors(include_input=False, include_url=False):
                    path = ".".join(str(p) for p in e["loc"])
                    line = f"  {path or '<root>'}: {e['msg']}"
                    origin = self._origin(path) if path else None
                    lines.append(f"{line} (from {origin})" if origin else line)
                raise ConfigValidationError(
                    exc, _redact(self._data), "\n" + "\n".join(lines)
                ) from exc

        # Generic fallback: call schema(**data)
        try:
            return schema(**self._data)
        except Exception as exc:
            raise ConfigValidationError(exc, _redact(self._data)) from exc

    # ------------------------------------------------------------------
    # Context manager for temporary overrides
    # ------------------------------------------------------------------

    @contextmanager
    def override(self, overrides: dict[str, Any]) -> Iterator[Config]:
        """
        Temporarily patch dot-path keys. Ideal for tests.

            with cfg.override({"app.debug": True, "database.pool_size": 1}):
                assert cfg.get("app.debug") is True
            # original values restored here

        The patch is applied to *this* object, so every reader of it sees
        the change, in every thread.  Because of that, overrides are
        serialised: while one thread is inside ``override()``, another
        thread entering it waits.  Nesting in one thread works.  The lock
        does not protect asyncio tasks that interleave in a single thread;
        for code that runs concurrently use :meth:`with_overrides`, which
        returns a modified copy and shares no state.

        Parameters
        ----------
        overrides: dict[str, Any]
            Mapping of dot-separated paths to override values.

        Raises :class:`FrozenConfigError` if the config is frozen.

        """
        self._check_frozen("override")
        with _OVERRIDE_LOCK:
            backup = copy.deepcopy(self._data)
            try:
                for path, value in overrides.items():
                    _set_path(self._data, path, value)
                yield self
            finally:
                object.__setattr__(self, "_data", backup)

    def with_overrides(self, overrides: Mapping[str, Any]) -> Config:
        """
        Return a copy of this config with dot-path *overrides* applied.

        Unlike :meth:`override` nothing is mutated, so it is safe to call
        from concurrent threads or tasks, and it also works on frozen
        configs (the copy stays frozen)::

            request_cfg = cfg.with_overrides({"app.debug": True})

        The overrides appear as a final ``<overrides>`` layer, so
        :meth:`explain` attributes those values to it.
        """
        data = copy.deepcopy(self._data)
        layer: dict[str, Any] = {}
        for path, value in overrides.items():
            _set_path(data, path, copy.deepcopy(value))
            _set_path(layer, path, copy.deepcopy(value))
        sources, layers = list(self._sources), list(self._layers)
        if overrides:
            sources.append("<overrides>")
            layers.append(("<overrides>", layer))
        return Config(data, sources, freeze=self._frozen, layers=layers)

    # ------------------------------------------------------------------
    # Dict-like access
    # ------------------------------------------------------------------

    def get(self, path: str, default: Any = _MISSING) -> Any:
        """
        Return the value at a dot-separated *path*.

        Supports dict keys, list indices, and any mix of both.

        Example dict:

            {
                "database": {
                    "url": "sqlite:///app.db",
                    "pool_size": 10
                },
                "server": {
                    "host": "localhost",
                    "allowed_hosts": ["myapp.com", "localhost"],
                }
            }

            cfg.get("database.pool_size")       # → 10
            cfg.get("server.allowed_hosts.0")   # → "myapp.com"
            cfg.get("server")                   # → full dict
            cfg.get("missing.key", "fallback")  # → "fallback"
            cfg.get("missing.key")              # → raises KeyError

        Parameters
        ----------
        path: str
            Dot-separated path to the desired value.
        default: Any, optional
            Value to return if the path is not found.  If not provided, a missing
            path will raise a KeyError.

        Returns
        -------
        Any
            The value at the specified path, or *default* if not found and *default*
            is provided.

        """
        value = _get_path(self._data, path, _MISSING)
        if value is _MISSING:
            if default is _MISSING:
                raise KeyError(path)
            return default
        return value

    def __getitem__(self, path: str) -> Any:
        return self.get(path)

    def __contains__(self, path: str) -> bool:
        return _get_path(self._data, path, _MISSING) is not _MISSING

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def __getattr__(self, name: str) -> Any:
        """Allow ``cfg.database.url``; real attributes and methods win."""
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            value = self._data[name]
        except KeyError:
            raise AttributeError(
                f"{type(self).__name__!r} has no key {name!r} "
                f"(keys: {list(self._data)})"
            ) from None
        if isinstance(value, dict):
            layers = [
                (src, d[name])
                for src, d in self._layers
                if isinstance(d.get(name), dict)
            ]
            return Config(value, self._sources, freeze=True, layers=layers)
        return value

    def _origin(self, path: str) -> str | None:
        """Source that supplied the winning value at *path*, if known."""
        for src, layer in reversed(self._layers):
            if _get_path(layer, path, _MISSING) is not _MISSING:
                return src
        return None

    def explain(self, path: str) -> Explanation:
        """
        Say where the value at dot-*path* came from.

        Returns an :class:`Explanation` with the winning source and the
        lower-priority sources it overrode.  Sensitive values are masked.

        Raises
        ------
        KeyError
            When *path* is not present in the config.

        """
        hits = [
            (src, found)
            for src, layer in self._layers
            if (found := _get_path(layer, path, _MISSING)) is not _MISSING
        ]
        if not hits:
            raise KeyError(path)
        return build_explanation(path, hits)

    def _with_reload(self, rebuild: Callable[[bool], Config]) -> Config:
        object.__setattr__(self, "_reload", rebuild)
        return self

    def reload(self, *, refresh_secrets: bool = True) -> Config:
        """
        Rebuild this config from the same inputs and return the new instance.

        Files, ``.env`` and environment variables are read again, and remote
        secrets are fetched fresh (pass ``refresh_secrets=False`` to let the
        ``secrets_ttl`` cache answer).  Nothing is mutated, so swap your
        reference: ``cfg = cfg.reload()``.  If anything fails the exception
        propagates and the old config stays valid.

        Only configs built by :meth:`from_dir` or :func:`imbrex.load_config`
        can be reloaded; others (``from_dict``, ``merge``, ``interpolate``,
        ``with_overrides`` ...) raise :class:`ImbrexError`.
        """
        if self._reload is None:
            raise ImbrexError(
                "This Config cannot be reloaded: only Config.from_dir() and "
                "imbrex.load_config() results remember how they were built."
            )
        return self._reload(refresh_secrets)

    def interpolate(self, *, env: Mapping[str, str] | None = None) -> Config:
        """
        Return a new Config with every ``${...}`` reference resolved.

        * ``${db.host}`` — another key (dot-path), resolved after merging.
        * ``${env:HOME}`` — an environment variable (*env*, default
          ``os.environ``).
        * ``${env:PORT:-8080}`` / ``${db.host:-localhost}`` — fallback used
          when the variable or key is missing.
        * ``$${`` — a literal ``${``.

        A value that is exactly one reference keeps the referenced type
        (``"${server.port}"`` → ``8080``); inside longer text the value is
        converted to ``str``.  :meth:`explain` reports the resolved values.

        Raises
        ------
        ConfigInterpolationError
            For a missing key or variable (without default) or a circular
            reference.

        """
        resolver = Resolver(self._data, os.environ if env is None else env)
        data: dict[str, Any] = resolver.resolve(self._data)
        layers = [
            (src, resolver.resolve(layer, lenient=True)) for src, layer in self._layers
        ]
        return Config(data, list(self._sources), freeze=self._frozen, layers=layers)

    def to_dict(self, *, redact: bool = False) -> dict[str, Any]:
        """
        Return a deep copy of the merged config as a plain dict.

        With ``redact=True`` values under sensitive-looking keys
        (``password``, ``*_token``, ``api_key``, ...) are replaced by ``***``,
        which makes the result safe to log or print.
        """
        import copy

        if redact:
            out: dict[str, Any] = _redact(self._data)
            return out
        return copy.deepcopy(self._data)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @classmethod
    def _load_files(
        cls,
        files: list[str] | list[Path],
        merge_strategy: MergeStrategy,
        key_strategies: dict[str, MergeStrategy] | None,
        freeze: bool = False,
    ) -> Config:
        if not files:
            return cls({}, [], freeze=freeze)

        dicts: list[dict[str, Any]] = []
        sources: list[str] = []

        for f in files:
            p = Path(f)
            dicts.append(parse_file(p))
            sources.append(str(p))

        merged = deep_merge(
            *dicts, strategy=merge_strategy, key_strategies=key_strategies
        )
        return cls(merged, sources, freeze=freeze, layers=list(zip(sources, dicts)))

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        top_keys = list(self._data.keys())
        return f"Config(keys={top_keys}, sources={self._sources})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Config):
            return self._data == other._data
        return NotImplemented
