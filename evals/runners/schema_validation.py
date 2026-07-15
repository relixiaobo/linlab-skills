"""Authoritative JSON Schema validation for evaluation-platform contracts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from evals.runners.errors import EvalConfigError


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def _jsonschema() -> tuple[Any, Any]:
    try:
        from jsonschema import Draft202012Validator
        from jsonschema.exceptions import SchemaError
    except ModuleNotFoundError as exc:
        raise EvalConfigError(
            "jsonschema is required for evaluation contracts; "
            "install it with: python3 -m pip install -r evals/requirements.txt"
        ) from exc
    return Draft202012Validator, SchemaError


def _schema_path(name: str) -> Path:
    if Path(name).name != name or not name.endswith(".schema.json"):
        raise EvalConfigError(f"invalid evaluation schema name: {name}")
    path = SCHEMA_DIR / name
    if not path.is_file() or path.is_symlink():
        raise EvalConfigError(f"missing evaluation schema: {path}")
    return path


@lru_cache(maxsize=None)
def schema_validator(name: str) -> Any:
    path = _schema_path(name)
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalConfigError(f"invalid schema JSON in {path}: {exc}") from exc
    validator_class, schema_error = _jsonschema()
    try:
        validator_class.check_schema(schema)
    except schema_error as exc:
        raise EvalConfigError(f"invalid JSON Schema in {path}: {exc.message}") from exc
    return validator_class(schema)


def _error_path(error: Any) -> str:
    parts = [str(part) for part in error.absolute_path]
    return ".".join(parts) if parts else "<root>"


def validate_document(value: Any, schema_name: str, label: str) -> None:
    errors = sorted(
        schema_validator(schema_name).iter_errors(value),
        key=lambda error: (tuple(str(part) for part in error.absolute_path), error.message),
    )
    if errors:
        error = errors[0]
        raise EvalConfigError(
            f"{label} violates {schema_name} at {_error_path(error)}: {error.message}"
        )


def validate_all_schemas() -> list[str]:
    names = [path.name for path in sorted(SCHEMA_DIR.glob("*.schema.json"))]
    if not names:
        raise EvalConfigError("no evaluation schemas found")
    for name in names:
        schema_validator(name)
    return names
