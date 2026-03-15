"""Tests for imbrex._exceptions."""

from __future__ import annotations

from pathlib import Path

import pytest

from imbrex._exceptions import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigSecretDescriptorError,
    ConfigValidationError,
    ImbrexError,
    SecretProviderError,
    UnsupportedFormatError,
)


class TestExceptionHierarchy:
    """All custom exceptions inherit from ImbrexError."""

    @pytest.mark.parametrize(
        "exc_cls",
        [
            UnsupportedFormatError,
            ConfigFileNotFoundError,
            ConfigParseError,
            ConfigValidationError,
            ConfigSecretDescriptorError,
            SecretProviderError,
        ],
    )
    def test_is_subclass_of_imbrex_error(self, exc_cls: type[ImbrexError]) -> None:
        assert issubclass(exc_cls, ImbrexError)

    def test_config_file_not_found_is_also_file_not_found_error(self) -> None:
        assert issubclass(ConfigFileNotFoundError, FileNotFoundError)


class TestUnsupportedFormatError:
    def test_message_contains_format(self) -> None:
        err = UnsupportedFormatError(".ini")
        assert ".ini" in str(err)

    def test_message_contains_supported_hint(self) -> None:
        err = UnsupportedFormatError(".ini", supported=[".toml", ".yaml"])
        assert ".toml" in str(err)
        assert ".yaml" in str(err)

    def test_fmt_attribute(self) -> None:
        err = UnsupportedFormatError("xml")
        assert err.fmt == "xml"


class TestConfigFileNotFoundError:
    def test_message_contains_path(self) -> None:
        err = ConfigFileNotFoundError("/missing/config.toml")
        assert "config.toml" in str(err)

    def test_path_attribute(self) -> None:
        err = ConfigFileNotFoundError("/some/path.toml")
        assert err.path == Path("/some/path.toml")

    def test_accepts_path_object(self) -> None:
        p = Path("/some/path.yaml")
        err = ConfigFileNotFoundError(p)
        assert err.path == p


class TestConfigParseError:
    def test_message_contains_path_and_cause(self) -> None:
        cause = ValueError("unexpected token")
        err = ConfigParseError("/bad/file.toml", cause)
        assert "file.toml" in str(err)
        assert "unexpected token" in str(err)

    def test_attributes(self) -> None:
        cause = RuntimeError("boom")
        err = ConfigParseError("/x.toml", cause)
        assert err.path == Path("/x.toml")
        assert err.cause is cause


class TestConfigValidationError:
    def test_message_contains_cause(self) -> None:
        cause = ValueError("missing field 'url'")
        err = ConfigValidationError(cause)
        assert "missing field" in str(err)

    def test_data_attribute(self) -> None:
        cause = ValueError("bad")
        data = {"key": "value"}
        err = ConfigValidationError(cause, data=data)
        assert err.data == data
        assert err.cause is cause

    def test_data_default_is_none(self) -> None:
        err = ConfigValidationError(ValueError("x"))
        assert err.data is None


class TestConfigSecretDescriptorError:
    def test_message_contains_path_and_cause(self) -> None:
        cause = ValueError("missing aws.region_name")
        err = ConfigSecretDescriptorError("/bad/secrets.toml", cause)
        assert "secrets.toml" in str(err)
        assert "missing aws.region_name" in str(err)

    def test_attributes(self) -> None:
        cause = RuntimeError("boom")
        err = ConfigSecretDescriptorError("/x.toml", cause)
        assert err.path == Path("/x.toml")
        assert err.cause is cause


class TestSecretProviderError:
    def test_message_contains_provider_and_cause(self) -> None:
        cause = RuntimeError("network timeout")
        err = SecretProviderError("aws", cause)
        assert "aws" in str(err)
        assert "network timeout" in str(err)

    def test_attributes(self) -> None:
        cause = RuntimeError("boom")
        err = SecretProviderError("gcp", cause)
        assert err.provider == "gcp"
        assert err.cause is cause

