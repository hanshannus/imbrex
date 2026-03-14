"""
strata.Config — hierarchical configuration loader and validator.

The :class:`Config` object is an immutable wrapper around a merged ``dict``.
All loading is done through classmethods; the constructor is intentionally
private so the public API stays ergonomic::

    from strata import Config

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

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from strata._exceptions import (
    ConfigFileNotFoundError,
    ConfigValidationError,
    UnsupportedFormatError,
)
from strata._merge import MergeStrategy, deep_merge
from strata._parsers import (
    SUPPORTED_FORMATS,
    discover_files,
    parse_file,
    parse_string,
)
from strata._priority import DEFAULT_PRIORITY, sort_paths

# T = TypeVar("T")
T = TypeVar("T", bound=BaseModel)


class Config:
    __slots__ = ("_data", "_sources")

    def __init__(self, data: dict[str, Any], sources: list[str]) -> None:
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

        """
        # Deliberately no public __init__ — use classmethods.
        self._data: dict[str, Any] = data
        self._sources: list[str] = sources

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

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        return cls._load_files(
            [Path(f) for f in files],
            merge_strategy=merge_strategy,
            key_strategies=key_strategies,
        )

    @classmethod
    def from_yaml(
        cls,
        *files: str | Path,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        key_strategies: dict[str, MergeStrategy] | None = None,
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

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        return cls._load_files(
            [Path(f) for f in files],
            merge_strategy=merge_strategy,
            key_strategies=key_strategies,
        )

    @classmethod
    def from_json(
        cls,
        *files: str | Path,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        key_strategies: dict[str, MergeStrategy] | None = None,
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

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        return cls._load_files(
            [Path(f) for f in files],
            merge_strategy=merge_strategy,
            key_strategies=key_strategies,
        )

    @classmethod
    def from_file(
        cls,
        *files: str | Path,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        key_strategies: dict[str, MergeStrategy] | None = None,
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

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        return cls._load_files(
            [Path(f) for f in files],
            merge_strategy=merge_strategy,
            key_strategies=key_strategies,
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
    ) -> Config:
        """
        Discover and load all config files in *directory*.

        Sorted hierarchically so that higher-priority files override lower ones.

        Parameters
        ----------
        directory:
            Path to the config directory.
        extension:
            File extension to scan for (e.g. ``"toml"``, ``"yaml"``).
        env:
            Active environment name (e.g. ``"production"``).  Files whose
            priority tier is *above* this environment are excluded so loading
            with ``env="development"`` never silently applies production
            overrides.  Auto-detected from ``APP_ENV`` / ``ENV`` /
            ``ENVIRONMENT`` when *None*.
        order:
            Explicit list of file stems in load order, e.g.
            ``["defaults", "development", "production"]``.  When given,
            *only* these stems are loaded (in exactly this order) and the
            automatic priority sort is bypassed.
        recursive:
            Descend into sub-directories.
        priority_table:
            Custom priority entries merged on top of the built-in table.
        merge_strategy:
            Default merge strategy.
        key_strategies:
            Per-key merge strategy overrides.

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
        d = Path(directory)
        if not d.exists():
            raise ConfigFileNotFoundError(d)
        if not d.is_dir():
            raise NotADirectoryError(f"Expected a directory: {d}")

        ext = extension if extension.startswith(".") else f".{extension}"
        all_paths = discover_files(d, extension=ext, recursive=recursive)

        if order is not None:
            # Explicit stem ordering — ignore auto-priority
            stem_to_path = {p.stem.lower(): p for p in all_paths}
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
                all_paths,
                env=resolved_env,
                priority_table={**DEFAULT_PRIORITY, **(priority_table or {})},
            )

        return cls._load_files(
            sorted_paths, merge_strategy=merge_strategy, key_strategies=key_strategies
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
    ) -> Config:
        """
        Build a :class:`Config` from one or more plain dicts.

        Dicts are merged left-to-right; the *last* dict wins.

        Parameters
        ----------
        *dicts:
            One or more dicts to merge in order.
        merge_strategy:
            Default merge strategy for every key.
        key_strategies:
            Per-key overrides keyed by dot-separated paths, e.g.
            ``{"server.allowed_hosts": MergeStrategy.ADDITIVE}``.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        sources = [f"<dict:{i}>" for i in range(len(dicts))]
        merged = deep_merge(
            *dicts, strategy=merge_strategy, key_strategies=key_strategies
        )
        return cls(merged, sources)

    @classmethod
    def from_string(
        cls,
        content: str,
        *,
        fmt: str,
    ) -> Config:
        """
        Parse a raw *content* string.

        Parameters
        ----------
        content:
            Raw config text.
        fmt:
            Format identifier: ``"toml"``, ``"yaml"``, or ``"json"``.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        fmt = fmt.lower().strip(".")
        if fmt not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(fmt, SUPPORTED_FORMATS)
        data = parse_string(content, fmt=fmt)
        return cls(data, [f"<string:{fmt}>"])

    @classmethod
    def from_env(
        cls,
        prefix: str = "",
        *,
        separator: str = "__",
    ) -> Config:
        """
        Build a :class:`Config` from environment variables.

        Variable names are lower-cased and *separator* (default ``__``) is
        converted to nested dict keys::

            APP_DATABASE__URL=postgres://host/db
            → {"database": {"url": "postgres://host/db"}}

        Parameters
        ----------
        prefix:
            Only variables beginning with *prefix* are included.
            The prefix itself is stripped before key conversion.
        separator:
            Nesting separator in variable names.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        data: dict[str, Any] = {}
        prefix_upper = prefix.upper()

        for raw_key, value in os.environ.items():
            if prefix_upper and not raw_key.upper().startswith(prefix_upper):
                continue
            stripped = raw_key[len(prefix) :] if prefix else raw_key
            parts = stripped.lower().split(separator.lower())
            node: dict[str, Any] = data
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value

        return cls(data, [f"<env prefix={prefix!r}>"])

    # ------------------------------------------------------------------
    # Classmethod — merge existing Config objects
    # ------------------------------------------------------------------

    @classmethod
    def merge(
        cls,
        *configs: Config,
        merge_strategy: MergeStrategy = MergeStrategy.REPLACE,
        key_strategies: dict[str, MergeStrategy] | None = None,
    ) -> Config:
        """
        Merge multiple :class:`Config` objects into one.

        The *last* config has the highest priority.

        Parameters
        ----------
        *configs:
            One or more Config instances to merge in order.
        merge_strategy:
            Default merge strategy for every key.
        key_strategies:
            Per-key overrides keyed by dot-separated paths, e.g.
            ``{"server.allowed_hosts": MergeStrategy.ADDITIVE}``.

        Returns
        -------
        Config
            Instance of ``Config`` containing the merged configuration.

        """
        dicts = [c._data for c in configs]
        sources = [src for c in configs for src in c._sources]
        merged = deep_merge(
            *dicts, strategy=merge_strategy, key_strategies=key_strategies
        )
        return cls(merged, sources)

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
        schema:
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
            from pydantic import BaseModel, ValidationError

            if isinstance(schema, type) and issubclass(schema, BaseModel):
                try:
                    return cast(T, schema.model_validate(self._data))
                except ValidationError as exc:
                    raise ConfigValidationError(exc, self._data) from exc

        except ImportError:
            pass  # Pydantic not installed — fall through to generic callable

        # Generic fallback: call schema(**data)
        try:
            return cast(T, schema(**self._data))
        except Exception as exc:
            raise ConfigValidationError(exc, self._data) from exc

    # ------------------------------------------------------------------
    # Dict-like access
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return the top-level value for *key*, or *default* if absent."""
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def to_dict(self) -> dict[str, Any]:
        """Return a deep copy of the merged config as a plain dict."""
        import copy

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
    ) -> Config:
        if not files:
            return cls({}, [])

        dicts: list[dict[str, Any]] = []
        sources: list[str] = []

        for f in files:
            p = Path(f)
            dicts.append(parse_file(p))
            sources.append(str(p))

        merged = deep_merge(
            *dicts, strategy=merge_strategy, key_strategies=key_strategies
        )
        return cls(merged, sources)

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
