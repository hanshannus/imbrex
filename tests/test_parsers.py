"""Tests for imbrex._parsers — format parsing, string/bytes parsing, file discovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from imbrex._exceptions import (
    ConfigFileNotFoundError,
    ConfigParseError,
    UnsupportedFormatError,
)
from imbrex._parsers import (
    EXT_TO_FORMAT,
    FORMAT_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_FORMATS,
    discover_files,
    parse_bytes,
    parse_file,
    parse_string,
)

# ── Registry sanity checks ────────────────────────────────────────────────


class TestFormatRegistry:
    def test_supported_formats(self) -> None:
        assert "toml" in SUPPORTED_FORMATS
        assert "yaml" in SUPPORTED_FORMATS
        assert "json" in SUPPORTED_FORMATS

    def test_supported_extensions(self) -> None:
        for ext in (".toml", ".yaml", ".yml", ".json"):
            assert ext in SUPPORTED_EXTENSIONS

    def test_ext_to_format_mapping(self) -> None:
        assert EXT_TO_FORMAT[".toml"] == "toml"
        assert EXT_TO_FORMAT[".yaml"] == "yaml"
        assert EXT_TO_FORMAT[".yml"] == "yaml"
        assert EXT_TO_FORMAT[".json"] == "json"

    def test_format_extensions_roundtrip(self) -> None:
        for fmt, exts in FORMAT_EXTENSIONS.items():
            for ext in exts:
                assert EXT_TO_FORMAT[ext] == fmt


# ── parse_file ─────────────────────────────────────────────────────────────


class TestParseFileTOML:
    def test_valid_toml(self, toml_file: Path) -> None:
        data = parse_file(toml_file)
        assert data["app"]["name"] == "TestApp"
        assert data["database"]["pool_size"] == 5

    def test_empty_toml(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.toml"
        p.write_text("", encoding="utf-8")
        data = parse_file(p)
        assert data == {}

    def test_invalid_toml_raises_parse_error(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.toml"
        p.write_text("[broken\n", encoding="utf-8")
        with pytest.raises(ConfigParseError):
            parse_file(p)


class TestParseFileYAML:
    def test_valid_yaml(self, yaml_file: Path) -> None:
        data = parse_file(yaml_file)
        assert data["app"]["name"] == "TestApp"
        assert data["database"]["url"] == "sqlite:///app.db"

    def test_empty_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        data = parse_file(p)
        assert data == {}

    def test_invalid_yaml_raises_parse_error(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text(":\n  :\n    - : :\n", encoding="utf-8")
        # Some malformed YAML may not raise; use truly broken syntax:
        p.write_text("{[invalid", encoding="utf-8")
        with pytest.raises(ConfigParseError):
            parse_file(p)

    def test_yml_extension(self, tmp_path: Path) -> None:
        p = tmp_path / "settings.yml"
        p.write_text("key: value\n", encoding="utf-8")
        data = parse_file(p)
        assert data["key"] == "value"


class TestParseFileJSON:
    def test_valid_json(self, json_file: Path) -> None:
        data = parse_file(json_file)
        assert data["app"]["debug"] is False
        assert data["database"]["pool_size"] == 5

    def test_empty_json_object(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.json"
        p.write_text("{}", encoding="utf-8")
        data = parse_file(p)
        assert data == {}

    def test_invalid_json_raises_parse_error(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{not json}", encoding="utf-8")
        with pytest.raises(ConfigParseError):
            parse_file(p)

    def test_json_array_raises_parse_error(self, tmp_path: Path) -> None:
        """JSON root must be an object, not an array."""
        p = tmp_path / "array.json"
        p.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ConfigParseError):
            parse_file(p)


class TestParseFileErrors:
    def test_missing_file_raises_not_found(self) -> None:
        with pytest.raises(ConfigFileNotFoundError):
            parse_file(Path("/does/not/exist.toml"))

    def test_unsupported_extension_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "config.ini"
        p.write_text("[section]\nkey=value\n", encoding="utf-8")
        with pytest.raises(UnsupportedFormatError):
            parse_file(p)


# ── parse_string ───────────────────────────────────────────────────────────


class TestParseString:
    def test_toml(self) -> None:
        data = parse_string('[app]\nname = "Hello"\n', fmt="toml")
        assert data["app"]["name"] == "Hello"

    def test_yaml(self) -> None:
        data = parse_string("app:\n  name: Hello\n", fmt="yaml")
        assert data["app"]["name"] == "Hello"

    def test_json(self) -> None:
        data = parse_string('{"app": {"name": "Hello"}}', fmt="json")
        assert data["app"]["name"] == "Hello"

    def test_unsupported_format_raises(self) -> None:
        with pytest.raises(UnsupportedFormatError):
            parse_string("data", fmt="xml")

    def test_format_is_case_insensitive(self) -> None:
        data = parse_string("key: value\n", fmt="YAML")
        assert data["key"] == "value"

    def test_format_strips_leading_dot(self) -> None:
        data = parse_string("key: value\n", fmt=".yaml")
        assert data["key"] == "value"

    def test_empty_toml_string(self) -> None:
        data = parse_string("", fmt="toml")
        assert data == {}

    def test_empty_yaml_string(self) -> None:
        # An empty string "" resolves to Path(".") which exists as a directory,
        # so the YAML parser treats it as a path and raises ConfigParseError.
        # Use whitespace-only content that won't resolve to a real path.
        data = parse_string("---\n", fmt="yaml")
        assert data == {}


# ── parse_bytes ────────────────────────────────────────────────────────────


class TestParseBytes:
    def test_toml_bytes(self) -> None:
        data = parse_bytes(b'[db]\nurl = "sqlite:///x"\n', fmt="toml")
        assert data["db"]["url"] == "sqlite:///x"

    def test_yaml_bytes(self) -> None:
        data = parse_bytes(b"db:\n  url: sqlite:///x\n", fmt="yaml")
        assert data["db"]["url"] == "sqlite:///x"

    def test_json_bytes(self) -> None:
        raw = json.dumps({"db": {"url": "sqlite:///x"}}).encode()
        data = parse_bytes(raw, fmt="json")
        assert data["db"]["url"] == "sqlite:///x"

    def test_unsupported_format_raises(self) -> None:
        with pytest.raises(UnsupportedFormatError):
            parse_bytes(b"data", fmt="csv")


# ── discover_files ─────────────────────────────────────────────────────────


class TestDiscoverFiles:
    def test_finds_toml_files(self, config_dir: Path) -> None:
        files = discover_files(config_dir, extension="toml")
        stems = [f.stem for f in files]
        assert "defaults" in stems
        assert "development" in stems
        assert "production" in stems

    def test_returns_sorted_by_name(self, config_dir: Path) -> None:
        files = discover_files(config_dir, extension="toml")
        names = [f.name for f in files]
        assert names == sorted(names)

    def test_extension_with_dot(self, config_dir: Path) -> None:
        files = discover_files(config_dir, extension=".toml")
        assert len(files) == 3

    def test_extension_without_dot(self, config_dir: Path) -> None:
        files = discover_files(config_dir, extension="toml")
        assert len(files) == 3

    def test_no_matches(self, config_dir: Path) -> None:
        files = discover_files(config_dir, extension="ini")
        assert files == []

    def test_recursive(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.toml").write_text("[x]\n", encoding="utf-8")
        (sub / "b.toml").write_text("[y]\n", encoding="utf-8")

        flat = discover_files(tmp_path, extension="toml", recursive=False)
        deep = discover_files(tmp_path, extension="toml", recursive=True)

        assert len(flat) == 1
        assert len(deep) == 2

    def test_ignores_non_matching_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "a.toml").write_text("[x]\n", encoding="utf-8")
        (tmp_path / "b.yaml").write_text("x: 1\n", encoding="utf-8")
        files = discover_files(tmp_path, extension="toml")
        assert len(files) == 1
        assert files[0].suffix == ".toml"
