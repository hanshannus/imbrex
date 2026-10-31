"""``.env`` loading and env-value coercion."""

from __future__ import annotations

from pathlib import Path

import pytest

from imbrex import Config, ConfigFileNotFoundError
from imbrex._env import coerce_value


class TestCoerceValue:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("true", True),
            ("False", False),
            ("42", 42),
            ("-7", -7),
            ("3.14", 3.14),
            ("1e3", "1e3"),
            ("007", "007"),
            ("[1, 2]", [1, 2]),
            ('{"a": 1}', {"a": 1}),
            ("[broken", "[broken"),
            ("hello", "hello"),
            ("", ""),
        ],
    )
    def test_cases(self, raw: str, expected: object) -> None:
        assert coerce_value(raw) == expected


class TestFromEnvCoerce:
    def test_off_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_PORT", "8080")
        assert Config.from_env("APP_")["port"] == "8080"

    def test_coerce(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_PORT", "8080")
        monkeypatch.setenv("APP_DB__ECHO", "true")
        cfg = Config.from_env("APP_", coerce=True)
        assert cfg["port"] == 8080
        assert cfg["db.echo"] is True


class TestFromDotenv:
    def test_nested_keys_and_prefix(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("APP_DATABASE__URL=pg://x\nAPP_DEBUG=1\nOTHER=nope\n")
        cfg = Config.from_dotenv(f, prefix="APP_")
        assert cfg.to_dict() == {"database": {"url": "pg://x"}, "debug": "1"}
        assert cfg.sources == [str(f)]

    def test_coerce(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("PORT=5432\n")
        assert Config.from_dotenv(f, coerce=True)["port"] == 5432

    def test_does_not_touch_os_environ(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("IMBREX_PROBE", raising=False)
        f = tmp_path / ".env"
        f.write_text("IMBREX_PROBE=1\n")
        Config.from_dotenv(f)
        import os

        assert "IMBREX_PROBE" not in os.environ

    def test_missing_required_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigFileNotFoundError):
            Config.from_dotenv(tmp_path / ".env")

    def test_missing_optional_is_empty(self, tmp_path: Path) -> None:
        cfg = Config.from_dotenv(tmp_path / ".env", required=False)
        assert cfg.to_dict() == {}
        assert cfg.sources == []

    def test_quotes_and_comments(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text('# c\nNAME="a b"\nEMPTY=\n')
        cfg = Config.from_dotenv(f)
        assert cfg["name"] == "a b"
