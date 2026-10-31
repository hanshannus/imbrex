"""``imbrex`` command line: inspect, explain, validate and diff configuration."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from imbrex._config import Config
from imbrex._exceptions import ImbrexError
from imbrex._load import load_config
from imbrex._redact import REDACTED, is_sensitive, redact

_DEFAULT_DIR = "config"


def _sources_parser() -> argparse.ArgumentParser:
    """Options shared by every command: where the config comes from."""
    p = argparse.ArgumentParser(add_help=False)
    g = p.add_argument_group("sources")
    g.add_argument(
        "--prefix", default="", help="read env vars / .env entries with this prefix"
    )
    g.add_argument("--dotenv", default=".env", help="dotenv file (default: .env)")
    g.add_argument("--no-dotenv", action="store_true", help="do not read a dotenv file")
    g.add_argument("--extension", help="toml, yaml or json (default: auto-detect)")
    return p


def _add_env(p: argparse.ArgumentParser) -> None:
    p.add_argument("--env", help="environment tier, e.g. production")


def _add_dir(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "directory",
        nargs="?",
        help=f"config directory (default: ./{_DEFAULT_DIR} if it exists)",
    )


def _build_parser() -> argparse.ArgumentParser:
    common = _sources_parser()
    parser = argparse.ArgumentParser(
        prog="imbrex", description="Inspect and check layered configuration."
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    show = sub.add_parser("show", parents=[common], help="print the merged config")
    _add_dir(show)
    _add_env(show)
    show.add_argument("--format", choices=["json", "yaml"], default="json")
    show.add_argument(
        "--reveal", action="store_true", help="do not mask sensitive values"
    )

    explain = sub.add_parser(
        "explain", parents=[common], help="say where a value came from"
    )
    explain.add_argument("key", help="dot-path, e.g. database.url")
    _add_dir(explain)
    _add_env(explain)

    validate = sub.add_parser(
        "validate", parents=[common], help="validate against a Pydantic model"
    )
    validate.add_argument("schema", help="import path, e.g. myapp.settings:Settings")
    _add_dir(validate)
    _add_env(validate)

    diff = sub.add_parser(
        "diff", parents=[common], help="compare the config of two environments"
    )
    diff.add_argument("directory", help="config directory")
    diff.add_argument("env_a", help="first environment")
    diff.add_argument("env_b", help="second environment")
    return parser


def _load(args: argparse.Namespace, env: str | None) -> Config:
    directory = args.directory
    if directory is None and Path(_DEFAULT_DIR).is_dir():
        directory = _DEFAULT_DIR
    return load_config(
        directory,
        env=env,
        env_prefix=args.prefix,
        dotenv=None if args.no_dotenv else args.dotenv,
        extension=args.extension,
    )


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict) and value:
            out.update(_flatten(value, f"{path}."))
        else:
            out[path] = value
    return out


def _shown(path: str, value: Any) -> str:
    masked = any(is_sensitive(part) for part in path.split("."))
    return repr(REDACTED if masked else value)


def _cmd_show(args: argparse.Namespace) -> int:
    data = _load(args, args.env).to_dict()
    if not args.reveal:
        data = redact(data)
    if args.format == "yaml":
        sys.stdout.write(yaml.safe_dump(data, sort_keys=False))
    else:
        print(json.dumps(data, indent=2, default=str))
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    cfg = _load(args, args.env)
    try:
        print(cfg.explain(args.key))
    except KeyError:
        print(f"error: key not found: {args.key}", file=sys.stderr)
        return 1
    return 0


def _import_schema(spec: str) -> Any:
    module_name, sep, attr = spec.partition(":")
    if not sep or not module_name or not attr:
        raise ImbrexError(f"schema must look like 'module:Class', got {spec!r}")
    sys.path.insert(0, os.getcwd())  # console scripts do not include the cwd
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ImbrexError(f"cannot import {module_name!r}: {exc}") from exc
    try:
        return getattr(module, attr)
    except AttributeError:
        raise ImbrexError(f"{module_name!r} has no attribute {attr!r}") from None


def _cmd_validate(args: argparse.Namespace) -> int:
    schema = _import_schema(args.schema)
    _load(args, args.env).validate(schema)
    print(f"OK: config is valid for {args.schema}")
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    a = _flatten(_load(args, args.env_a).to_dict())
    b = _flatten(_load(args, args.env_b).to_dict())
    lines: list[str] = []
    for path in sorted(a.keys() | b.keys()):
        if path not in b:
            lines.append(f"- {path} = {_shown(path, a[path])}")
        elif path not in a:
            lines.append(f"+ {path} = {_shown(path, b[path])}")
        elif a[path] != b[path]:
            if any(is_sensitive(part) for part in path.split(".")):
                lines.append(f"~ {path}: (changed, value hidden)")
            else:
                lines.append(f"~ {path}: {a[path]!r} -> {b[path]!r}")
    if lines:
        print(f"--- {args.env_a}\n+++ {args.env_b}")
        print("\n".join(lines))
    else:
        print(f"no differences between {args.env_a} and {args.env_b}")
    return 0


_COMMANDS = {
    "show": _cmd_show,
    "explain": _cmd_explain,
    "validate": _cmd_validate,
    "diff": _cmd_diff,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``imbrex`` command. Returns the process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        return _COMMANDS[args.command](args)
    except ImbrexError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
