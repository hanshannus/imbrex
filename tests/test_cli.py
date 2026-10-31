"""The ``imbrex`` command line."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from imbrex._cli import main


@pytest.fixture
def cfg_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "config"
    d.mkdir()
    (d / "defaults.toml").write_text(
        '[database]\nurl = "sqlite:///d"\npool_size = 5\npassword = "pw0"\n'
        '[server]\nhosts = ["a"]\n'
    )
    (d / "staging.toml").write_text('[database]\nurl = "pg://staging"\n')
    (d / "production.toml").write_text(
        '[database]\nurl = "pg://prod"\npassword = "pw1"\n[cache]\nttl = 60\n'
    )
    monkeypatch.chdir(tmp_path)
    for k in ("APP_ENV", "ENV", "ENVIRONMENT"):
        monkeypatch.delenv(k, raising=False)
    return d


class TestShow:
    def test_json_default_masks_secrets(
        self, cfg_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["show", str(cfg_dir), "--env", "production"]) == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["database"]["url"] == "pg://prod"
        assert data["database"]["password"] == "***"
        assert "pw1" not in out

    def test_reveal(self, cfg_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        main(["show", str(cfg_dir), "--env", "production", "--reveal"])
        assert json.loads(capsys.readouterr().out)["database"]["password"] == "pw1"

    def test_yaml_format(
        self, cfg_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["show", str(cfg_dir), "--env", "staging", "--format", "yaml"])
        assert "url: pg://staging" in capsys.readouterr().out

    def test_defaults_to_config_dir_in_cwd(
        self, cfg_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["show", "--env", "staging"])
        assert json.loads(capsys.readouterr().out)["database"]["url"] == "pg://staging"

    def test_env_prefix_and_dotenv(
        self,
        cfg_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        Path(".env").write_text("APP_DATABASE__POOL_SIZE=7\n")
        monkeypatch.setenv("APP_DATABASE__URL", "pg://env")
        main(["show", "--env", "staging", "--prefix", "APP_"])
        data = json.loads(capsys.readouterr().out)
        assert data["database"]["pool_size"] == 7
        assert data["database"]["url"] == "pg://env"

    def test_no_dotenv_flag(
        self, cfg_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        Path(".env").write_text("DATABASE__POOL_SIZE=7\n")
        main(["show", "--no-dotenv"])
        assert json.loads(capsys.readouterr().out)["database"]["pool_size"] == 5


class TestExplain:
    def test_prints_provenance(
        self, cfg_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert (
            main(["explain", "database.url", str(cfg_dir), "--env", "production"]) == 0
        )
        out = capsys.readouterr().out
        assert "production.toml" in out and "defaults.toml" in out

    def test_missing_key_exits_1(
        self, cfg_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["explain", "nope", str(cfg_dir)]) == 1
        assert "nope" in capsys.readouterr().err

    def test_secret_masked(
        self, cfg_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["explain", "database.password", str(cfg_dir), "--env", "production"])
        out = capsys.readouterr().out
        assert "***" in out and "pw1" not in out


class TestValidate:
    @pytest.fixture
    def schema_mod(self, cfg_dir: Path) -> None:
        Path("myschema.py").write_text(
            "from pydantic import BaseModel\n"
            "class DB(BaseModel):\n    url: str\n    pool_size: int\n"
            "class Good(BaseModel):\n    database: DB\n"
            "class Bad(BaseModel):\n    database: DB\n    missing_key: str\n"
        )

    def test_valid(
        self,
        schema_mod: None,
        cfg_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert main(["validate", "myschema:Good", str(cfg_dir)]) == 0
        assert "valid" in capsys.readouterr().out.lower()

    def test_invalid_lists_paths_and_exits_1(
        self,
        schema_mod: None,
        cfg_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert main(["validate", "myschema:Bad", str(cfg_dir)]) == 1
        assert "missing_key" in capsys.readouterr().err

    @pytest.mark.parametrize("spec", ["nocolon", "nope_mod:X", "myschema:Nope"])
    def test_bad_spec_exits_1(
        self,
        spec: str,
        schema_mod: None,
        cfg_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert main(["validate", spec, str(cfg_dir)]) == 1
        assert capsys.readouterr().err


class TestDiff:
    def test_shows_added_removed_changed(
        self, cfg_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["diff", str(cfg_dir), "staging", "production"]) == 0
        out = capsys.readouterr().out
        assert "~ database.url: 'pg://staging' -> 'pg://prod'" in out
        assert "+ cache.ttl = 60" in out
        assert "database.pool_size" not in out  # identical in both

    def test_secret_difference_reported_but_masked(
        self, cfg_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["diff", str(cfg_dir), "staging", "production"])
        out = capsys.readouterr().out
        assert "database.password" in out
        assert "pw0" not in out and "pw1" not in out

    def test_identical_envs(
        self, cfg_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["diff", str(cfg_dir), "staging", "staging"]) == 0
        assert "no differences" in capsys.readouterr().out.lower()


class TestErrors:
    def test_missing_directory_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["show", str(tmp_path / "nope")]) == 1
        assert "nope" in capsys.readouterr().err

    def test_no_command_prints_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 2


def test_python_dash_m(cfg_dir: Path) -> None:
    r = subprocess.run(
        [sys.executable, "-m", "imbrex", "show", str(cfg_dir), "--env", "staging"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["database"]["url"] == "pg://staging"
