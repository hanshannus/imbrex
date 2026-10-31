"""imbrex must import and work when Pydantic is not installed."""

from __future__ import annotations

import subprocess
import sys
import textwrap

_PRELUDE = "import sys; sys.modules['pydantic'] = None\n"


def _run(body: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _PRELUDE + textwrap.dedent(body)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_import_and_load_without_pydantic() -> None:
    r = _run(
        """
        import imbrex
        cfg = imbrex.Config.from_dict({"db": {"url": "x"}})
        assert cfg.db.url == "x"
        assert "pydantic" not in [m for m in sys.modules if sys.modules[m]]
        """
    )
    assert r.returncode == 0, r.stderr


def test_validate_plain_callable_without_pydantic() -> None:
    r = _run(
        """
        from dataclasses import dataclass
        import imbrex

        @dataclass
        class S:
            name: str

        assert imbrex.Config.from_dict({"name": "a"}).validate(S).name == "a"
        try:
            imbrex.Config.from_dict({}).validate(S)
        except imbrex.ConfigValidationError:
            pass
        else:
            raise SystemExit("expected ConfigValidationError")
        """
    )
    assert r.returncode == 0, r.stderr


def test_from_dir_without_secrets_does_not_need_pydantic(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "defaults.toml").write_text("a = 1\n")
    r = _run(
        f"""
        import imbrex
        assert imbrex.Config.from_dir({str(tmp_path)!r})["a"] == 1
        """
    )
    assert r.returncode == 0, r.stderr
