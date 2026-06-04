from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique

DATA_SOURCE_VALIDATION_ERROR = "DATA_SOURCE_VALIDATION_ERROR"


def load_data_sources(path: Path) -> dict[str, Any]:
    payload = load_yaml_unique(Path(path))
    if not isinstance(payload, dict):
        raise WorkbenchException(DATA_SOURCE_VALIDATION_ERROR, f"Data sources must be a mapping: {path}")
    return payload


def validate_data_sources(path: Path, schema_dir: Path) -> dict[str, Any]:
    payload = load_data_sources(path)
    schema = load_yaml_unique(Path(schema_dir) / "data_source.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(DATA_SOURCE_VALIDATION_ERROR, f"{path}{suffix}: {first.message}")
    return payload


def credential_env_names(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in (payload.get("data_sources") or {}).values():
        credentials = item.get("credentials")
        if isinstance(credentials, dict):
            names.extend(str(value) for value in credentials.get("required_env") or [])
    return names
