from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique

TOOL_REGISTRY_ERROR = "TOOL_REGISTRY_ERROR"


def _validate(schema: dict[str, Any], payload: dict[str, Any], label: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.path)
        suffix = f" at {path}" if path else ""
        raise WorkbenchException(TOOL_REGISTRY_ERROR, f"{label}{suffix}: {first.message}")


def load_tool_registry(path: Path, schema_dir: Path) -> dict[str, Any]:
    path = Path(path)
    payload = load_yaml_unique(path)
    if not isinstance(payload, dict):
        raise WorkbenchException(TOOL_REGISTRY_ERROR, f"Tool registry must be a mapping: {path}")
    schema = load_yaml_unique(Path(schema_dir) / "tool.schema.json")
    _validate(schema, payload, str(path))
    return payload


def registered_tool_ids(registry: dict[str, Any]) -> set[str]:
    return set((registry.get("tools") or {}).keys())
