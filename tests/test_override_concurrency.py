"""``override()`` under concurrency and the ``with_overrides()`` derived copy."""

from __future__ import annotations

import threading
import time

import pytest

from imbrex import Config, FrozenConfigError


class TestOverrideThreadSafety:
    def test_interleaved_overrides_do_not_leak(self) -> None:
        cfg = Config.from_dict({"a": 1, "b": 1})
        a_in, b_in, a_out = (threading.Event() for _ in range(3))

        def first() -> None:
            with cfg.override({"a": 2}):
                a_in.set()
                b_in.wait(timeout=0.3)  # unsafe code: B is in by now
            a_out.set()

        def second() -> None:
            a_in.wait()
            with cfg.override({"b": 2}):
                b_in.set()
                a_out.wait(timeout=1)  # leave *after* A: non-LIFO exit

        threads = [threading.Thread(target=first), threading.Thread(target=second)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert cfg.to_dict() == {"a": 1, "b": 1}

    def test_many_threads_restore_original(self) -> None:
        cfg = Config.from_dict({"n": 0})

        def work(i: int) -> None:
            for _ in range(50):
                with cfg.override({"n": i}):
                    time.sleep(0.0002)  # let other threads try to interleave
                    assert cfg["n"] == i

        threads = [threading.Thread(target=work, args=(i,)) for i in range(1, 6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert cfg["n"] == 0

    def test_nested_in_same_thread_still_works(self) -> None:
        cfg = Config.from_dict({"a": 1})
        with cfg.override({"a": 2}):
            with cfg.override({"a": 3}):
                assert cfg["a"] == 3
            assert cfg["a"] == 2
        assert cfg["a"] == 1


class TestWithOverrides:
    def test_returns_new_config_original_untouched(self) -> None:
        cfg = Config.from_dict({"app": {"debug": False, "workers": 2}})
        out = cfg.with_overrides({"app.debug": True})
        assert out is not cfg
        assert out["app.debug"] is True and out["app.workers"] == 2
        assert cfg["app.debug"] is False

    def test_creates_nested_keys(self) -> None:
        out = Config.from_dict({}).with_overrides({"a.b.c": 1})
        assert out.to_dict() == {"a": {"b": {"c": 1}}}

    def test_works_on_frozen_and_stays_frozen(self) -> None:
        cfg = Config.from_dict({"a": 1}, freeze=True)
        out = cfg.with_overrides({"a": 2})
        assert out["a"] == 2 and out.is_frozen and cfg["a"] == 1
        with pytest.raises(FrozenConfigError):
            with out.override({"a": 3}):
                pass

    def test_value_is_copied(self) -> None:
        extra = {"x": [1]}
        out = Config.from_dict({}).with_overrides({"k": extra})
        extra["x"].append(2)
        assert out["k"] == {"x": [1]}

    def test_explain_attributes_to_overrides(self) -> None:
        cfg = Config.from_dict({"a": 1}).with_overrides({"a": 2})
        ex = cfg.explain("a")
        assert ex.value == 2 and ex.source == "<overrides>"
        assert ex.overridden == [("<dict:0>", 1)]
        assert cfg.sources == ["<dict:0>", "<overrides>"]

    def test_empty_is_equal_copy(self) -> None:
        cfg = Config.from_dict({"a": 1})
        out = cfg.with_overrides({})
        assert out == cfg and out is not cfg and out.sources == cfg.sources

    def test_safe_to_use_concurrently(self) -> None:
        cfg = Config.from_dict({"n": 0})
        seen: list[int] = []

        def work(i: int) -> None:
            seen.append(cfg.with_overrides({"n": i})["n"])

        threads = [threading.Thread(target=work, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sorted(seen) == list(range(20)) and cfg["n"] == 0
