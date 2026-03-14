"""Tests for strata._merge — deep-merge strategies and helpers."""

from __future__ import annotations

import pytest

from strata._merge import MergeStrategy, deep_merge


# ── Basic merge behaviour ──────────────────────────────────────────────────


class TestDeepMergeReplace:
    """REPLACE strategy: rightmost dict wins for scalars and lists."""

    def test_scalar_override(self) -> None:
        a = {"key": "old"}
        b = {"key": "new"}
        result = deep_merge(a, b, strategy=MergeStrategy.REPLACE)
        assert result["key"] == "new"

    def test_nested_dict_merge(self) -> None:
        a = {"db": {"url": "sqlite:///a", "pool": 5}}
        b = {"db": {"url": "pg://host/b"}}
        result = deep_merge(a, b, strategy=MergeStrategy.REPLACE)
        assert result["db"]["url"] == "pg://host/b"
        assert result["db"]["pool"] == 5

    def test_list_replaced(self) -> None:
        a = {"hosts": ["a", "b"]}
        b = {"hosts": ["c"]}
        result = deep_merge(a, b, strategy=MergeStrategy.REPLACE)
        assert result["hosts"] == ["c"]

    def test_new_key_added(self) -> None:
        a = {"x": 1}
        b = {"y": 2}
        result = deep_merge(a, b, strategy=MergeStrategy.REPLACE)
        assert result == {"x": 1, "y": 2}

    def test_empty_dicts(self) -> None:
        assert deep_merge() == {}
        assert deep_merge({}) == {}
        assert deep_merge({}, {}) == {}

    def test_single_dict(self) -> None:
        d = {"a": 1, "b": {"c": 2}}
        result = deep_merge(d, strategy=MergeStrategy.REPLACE)
        assert result == d

    def test_three_dicts(self) -> None:
        a = {"key": 1}
        b = {"key": 2}
        c = {"key": 3}
        result = deep_merge(a, b, c, strategy=MergeStrategy.REPLACE)
        assert result["key"] == 3

    def test_deeply_nested(self) -> None:
        a = {"l1": {"l2": {"l3": {"val": "old"}}}}
        b = {"l1": {"l2": {"l3": {"val": "new"}}}}
        result = deep_merge(a, b, strategy=MergeStrategy.REPLACE)
        assert result["l1"]["l2"]["l3"]["val"] == "new"


class TestDeepMergeAdditive:
    """ADDITIVE strategy: lists are concatenated, scalars replaced."""

    def test_lists_concatenated(self) -> None:
        a = {"hosts": ["a"]}
        b = {"hosts": ["b", "c"]}
        result = deep_merge(a, b, strategy=MergeStrategy.ADDITIVE)
        assert result["hosts"] == ["a", "b", "c"]

    def test_scalars_replaced(self) -> None:
        a = {"name": "old"}
        b = {"name": "new"}
        result = deep_merge(a, b, strategy=MergeStrategy.ADDITIVE)
        assert result["name"] == "new"


class TestDeepMergeTypesafe:
    """TYPESAFE strategy: raises TypeError on type mismatch."""

    def test_same_types_merge(self) -> None:
        a = {"port": 8000}
        b = {"port": 9000}
        result = deep_merge(a, b, strategy=MergeStrategy.TYPESAFE)
        assert result["port"] == 9000

    def test_type_mismatch_raises(self) -> None:
        a = {"port": 8000}
        b = {"port": "not-a-number"}
        with pytest.raises(TypeError, match="Type mismatch"):
            deep_merge(a, b, strategy=MergeStrategy.TYPESAFE)

    def test_nested_type_mismatch(self) -> None:
        a = {"db": {"pool": 5}}
        b = {"db": {"pool": "ten"}}
        with pytest.raises(TypeError, match="db.pool"):
            deep_merge(a, b, strategy=MergeStrategy.TYPESAFE)

    def test_new_keys_allowed(self) -> None:
        a = {"x": 1}
        b = {"y": "hello"}
        result = deep_merge(a, b, strategy=MergeStrategy.TYPESAFE)
        assert result == {"x": 1, "y": "hello"}

    def test_nested_dict_merged(self) -> None:
        a = {"db": {"url": "a", "pool": 5}}
        b = {"db": {"url": "b"}}
        result = deep_merge(a, b, strategy=MergeStrategy.TYPESAFE)
        assert result["db"]["url"] == "b"
        assert result["db"]["pool"] == 5


# ── Per-key strategy overrides ─────────────────────────────────────────────


class TestKeyStrategies:
    def test_additive_override_on_single_key(self) -> None:
        a = {"server": {"hosts": ["a"], "port": 80}}
        b = {"server": {"hosts": ["b"], "port": 443}}
        result = deep_merge(
            a,
            b,
            strategy=MergeStrategy.REPLACE,
            key_strategies={"server.hosts": MergeStrategy.ADDITIVE},
        )
        assert result["server"]["hosts"] == ["a", "b"]
        assert result["server"]["port"] == 443  # replaced, not additive

    def test_non_list_values_unaffected_by_additive_override(self) -> None:
        a = {"server": {"host": "old"}}
        b = {"server": {"host": "new"}}
        result = deep_merge(
            a,
            b,
            strategy=MergeStrategy.REPLACE,
            key_strategies={"server.host": MergeStrategy.ADDITIVE},
        )
        # Strings are not lists, so additive logic doesn't apply — value replaced.
        assert result["server"]["host"] == "new"

    def test_missing_key_in_base_does_not_crash(self) -> None:
        a: dict[str, object] = {}
        b = {"server": {"hosts": ["c"]}}
        result = deep_merge(
            a,
            b,
            strategy=MergeStrategy.REPLACE,
            key_strategies={"server.hosts": MergeStrategy.ADDITIVE},
        )
        assert result["server"]["hosts"] == ["c"]

    def test_missing_key_in_override_does_not_crash(self) -> None:
        a = {"server": {"hosts": ["a"]}}
        b: dict[str, object] = {}
        result = deep_merge(
            a,
            b,
            strategy=MergeStrategy.REPLACE,
            key_strategies={"server.hosts": MergeStrategy.ADDITIVE},
        )
        assert result["server"]["hosts"] == ["a"]


# ── MergeStrategy enum ────────────────────────────────────────────────────


class TestMergeStrategyEnum:
    def test_values(self) -> None:
        assert MergeStrategy.REPLACE.value == "replace"
        assert MergeStrategy.ADDITIVE.value == "additive"
        assert MergeStrategy.TYPESAFE.value == "typesafe"

    def test_members(self) -> None:
        names = [m.name for m in MergeStrategy]
        assert "REPLACE" in names
        assert "ADDITIVE" in names
        assert "TYPESAFE" in names

