"""Secret redaction in to_dict(), validation errors and exception data."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from imbrex import Config, ConfigValidationError
from imbrex._redact import REDACTED, redact


class DB(BaseModel):
    url: str
    password: str
    pool_size: int = 5


class Settings(BaseModel):
    database: DB
    api_token: str


DATA = {
    "database": {"url": "pg://x", "password": "hunter2", "pool_size": "many"},
    "api_token": "tok-123",
    "Items": [{"client_secret": "s3"}],
}


class TestRedact:
    def test_masks_sensitive_keys_recursively(self) -> None:
        out = redact(DATA)
        assert out["database"]["password"] == REDACTED
        assert out["api_token"] == REDACTED
        assert out["Items"][0]["client_secret"] == REDACTED

    def test_keeps_non_sensitive_values(self) -> None:
        out = redact(DATA)
        assert out["database"]["url"] == "pg://x"

    def test_does_not_mutate_input(self) -> None:
        redact(DATA)
        assert DATA["api_token"] == "tok-123"

    def test_keyed_mapping_is_masked_whole(self) -> None:
        assert redact({"credentials": {"a": 1}})["credentials"] == REDACTED


class TestToDict:
    def test_default_is_unredacted(self) -> None:
        assert Config.from_dict(DATA).to_dict()["api_token"] == "tok-123"

    def test_redact_flag(self) -> None:
        out = Config.from_dict(DATA).to_dict(redact=True)
        assert out["database"]["password"] == REDACTED


class TestValidationErrors:
    def test_message_has_key_path_and_no_values(self) -> None:
        cfg = Config.from_dict(DATA)
        with pytest.raises(ConfigValidationError) as exc:
            cfg.validate(Settings)
        text = str(exc.value)
        assert "database.pool_size" in text
        assert "hunter2" not in text
        assert "tok-123" not in text

    def test_missing_field_reported_by_path(self) -> None:
        cfg = Config.from_dict({"database": {"url": "x"}})
        with pytest.raises(ConfigValidationError) as exc:
            cfg.validate(Settings)
        text = str(exc.value)
        assert "database.password" in text
        assert "api_token" in text

    def test_data_attribute_is_redacted(self) -> None:
        cfg = Config.from_dict(DATA)
        with pytest.raises(ConfigValidationError) as exc:
            cfg.validate(Settings)
        assert exc.value.data is not None
        assert exc.value.data["api_token"] == REDACTED
        assert exc.value.data["database"]["url"] == "pg://x"

    def test_cause_chain_preserved(self) -> None:
        cfg = Config.from_dict(DATA)
        with pytest.raises(ConfigValidationError) as exc:
            cfg.validate(Settings)
        assert exc.value.cause is not None
