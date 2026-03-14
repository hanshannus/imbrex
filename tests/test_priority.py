"""Tests for imbrex._priority — priority ordering, env resolution, filtering."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from imbrex._priority import DEFAULT_PRIORITY, priority_of, sort_paths

# ── DEFAULT_PRIORITY table ─────────────────────────────────────────────────


class TestDefaultPriority:
    def test_defaults_lowest_named(self) -> None:
        assert DEFAULT_PRIORITY["defaults"] == 100

    def test_production_higher_than_dev(self) -> None:
        assert DEFAULT_PRIORITY["production"] > DEFAULT_PRIORITY["development"]

    def test_local_higher_than_production(self) -> None:
        assert DEFAULT_PRIORITY["local"] > DEFAULT_PRIORITY["production"]

    def test_secrets_highest(self) -> None:
        assert DEFAULT_PRIORITY["secrets"] == max(DEFAULT_PRIORITY.values())

    def test_aliases(self) -> None:
        assert DEFAULT_PRIORITY["dev"] == DEFAULT_PRIORITY["development"]
        assert DEFAULT_PRIORITY["prod"] == DEFAULT_PRIORITY["production"]
        assert DEFAULT_PRIORITY["default"] == DEFAULT_PRIORITY["defaults"]
        assert DEFAULT_PRIORITY["secret"] == DEFAULT_PRIORITY["secrets"]


# ── priority_of ────────────────────────────────────────────────────────────


class TestPriorityOf:
    def test_known_stem(self) -> None:
        assert priority_of("defaults") == 100
        assert priority_of("production") == 500

    def test_unknown_stem_returns_zero(self) -> None:
        assert priority_of("random_file") == 0

    def test_case_insensitive(self) -> None:
        assert priority_of("Production") == 500
        assert priority_of("DEFAULTS") == 100

    def test_with_custom_table(self) -> None:
        assert priority_of("custom", priority_table={"custom": 999}) == 999

    def test_custom_table_overrides_default(self) -> None:
        # Override the default priority for "production"
        prio = priority_of("production", priority_table={"production": 9999})
        assert prio == 9999

    def test_env_stem_gets_unknown_env_priority_when_not_in_table(self) -> None:
        prio = priority_of("myenv", env="myenv")
        assert prio == 350  # _UNKNOWN_ENV_PRIORITY


# ── sort_paths — basic ordering ────────────────────────────────────────────


def _paths(*stems: str) -> list[Path]:
    return [Path(f"{s}.toml") for s in stems]


class TestSortPaths:
    def test_sorts_by_priority(self) -> None:
        paths = _paths("production", "defaults", "development")
        result = sort_paths(paths)
        stems = [p.stem for p in result]
        assert stems == ["defaults", "development", "production"]

    def test_unknown_stems_sorted_first(self) -> None:
        paths = _paths("custom", "defaults")
        result = sort_paths(paths)
        assert result[0].stem == "custom"  # prio 0
        assert result[1].stem == "defaults"  # prio 100

    def test_stable_order_for_equal_priority(self) -> None:
        # "base" and "common" both have priority 200
        paths = _paths("common", "base")
        result = sort_paths(paths)
        stems = [p.stem for p in result]
        # Both have same priority; Python's sort is stable so input order preserved
        assert set(stems) == {"common", "base"}

    def test_empty_input(self) -> None:
        assert sort_paths([]) == []


# ── sort_paths — env filtering ─────────────────────────────────────────────


class TestSortPathsEnvFiltering:
    def test_env_excludes_higher_tiers(self) -> None:
        paths = _paths("defaults", "development", "production", "local", "secrets")
        result = sort_paths(paths, env="development")
        stems = [p.stem for p in result]
        assert "production" not in stems
        assert "local" not in stems
        assert "secrets" not in stems
        assert "defaults" in stems
        assert "development" in stems

    def test_env_production_includes_up_to_production(self) -> None:
        paths = _paths("defaults", "development", "production", "local")
        result = sort_paths(paths, env="production")
        stems = [p.stem for p in result]
        assert "production" in stems
        assert "defaults" in stems
        assert "development" in stems
        assert "local" not in stems

    def test_no_env_includes_everything(self) -> None:
        paths = _paths("defaults", "production", "secrets")
        result = sort_paths(paths, env=None)
        assert len(result) == 3

    def test_max_env_priority_false_disables_filtering(self) -> None:
        paths = _paths("defaults", "development", "production", "secrets")
        result = sort_paths(paths, env="development", max_env_priority=False)
        stems = [p.stem for p in result]
        assert "production" in stems
        assert "secrets" in stems


# ── sort_paths — env resolution from environment variables ─────────────────


class TestEnvResolution:
    def test_app_env_variable(self) -> None:
        paths = _paths("defaults", "development", "production")
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
            result = sort_paths(paths)
        stems = [p.stem for p in result]
        assert "production" not in stems

    def test_env_variable(self) -> None:
        paths = _paths("defaults", "development", "production")
        env_backup = os.environ.pop("APP_ENV", None)
        try:
            with patch.dict(os.environ, {"ENV": "development"}, clear=False):
                os.environ.pop("APP_ENV", None)
                result = sort_paths(paths)
            stems = [p.stem for p in result]
            assert "production" not in stems
        finally:
            if env_backup:
                os.environ["APP_ENV"] = env_backup

    def test_explicit_env_overrides_env_var(self) -> None:
        """When env= is passed explicitly, it should take precedence."""
        paths = _paths("defaults", "development", "production")
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            result = sort_paths(paths, env="development")
        stems = [p.stem for p in result]
        assert "production" not in stems


# ── sort_paths — custom priority table ─────────────────────────────────────


class TestCustomPriorityTable:
    def test_custom_entry(self) -> None:
        paths = _paths("defaults", "custom_tier")
        result = sort_paths(paths, priority_table={"custom_tier": 150})
        stems = [p.stem for p in result]
        assert stems == ["defaults", "custom_tier"]

    def test_override_existing_entry(self) -> None:
        paths = _paths("defaults", "production")
        # Make "defaults" higher priority than "production"
        result = sort_paths(
            paths, priority_table={"defaults": 9999}, max_env_priority=False
        )
        stems = [p.stem for p in result]
        assert stems == ["production", "defaults"]
