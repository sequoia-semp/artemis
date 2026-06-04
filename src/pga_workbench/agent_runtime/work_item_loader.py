from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from ..exceptions import WorkbenchException

WORK_ITEM_NOT_FOUND = "WORK_ITEM_NOT_FOUND"
WORK_ITEM_VALIDATION_ERROR = "WORK_ITEM_VALIDATION_ERROR"


def load_work_item(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise WorkbenchException(WORK_ITEM_NOT_FOUND, f"Work item not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise WorkbenchException(WORK_ITEM_VALIDATION_ERROR, f"Work item must be a mapping: {path}")
    return payload


def find_ticket(root: Path, ticket_id: str) -> Path:
    root = Path(root)
    candidates = sorted((root / "tickets").glob(f"{ticket_id}-*.yaml"))
    if not candidates:
        candidates = sorted((root / "tickets").glob(f"{ticket_id}.yaml"))
    if not candidates:
        raise WorkbenchException(WORK_ITEM_NOT_FOUND, f"Ticket not found: {ticket_id}")
    if len(candidates) > 1:
        raise WorkbenchException(WORK_ITEM_VALIDATION_ERROR, f"Multiple tickets match {ticket_id}: {candidates}")
    return candidates[0]


def load_ticket(root: Path, ticket_id: str) -> dict[str, Any]:
    return load_work_item(find_ticket(root, ticket_id))


def validate_work_item(path: Path, schema_dir: Path) -> None:
    payload = load_work_item(path)
    item_type = payload.get("type")
    schema_name = {
        "epic": "epic.schema.json",
        "sprint": "sprint.schema.json",
        "ticket": "ticket.schema.json",
    }.get(item_type)
    if schema_name is None:
        raise WorkbenchException(WORK_ITEM_VALIDATION_ERROR, f"Unsupported work item type: {item_type}")

    schema_dir = Path(schema_dir).resolve()
    common_schema = yaml.safe_load((schema_dir / "work_item.schema.json").read_text(encoding="utf-8"))
    schema = yaml.safe_load((schema_dir / schema_name).read_text(encoding="utf-8"))
    schemas = [common_schema, schema["allOf"][1] if "allOf" in schema else schema]
    errors = []
    for item_schema in schemas:
        errors.extend(Draft202012Validator(item_schema).iter_errors(payload))
    errors = sorted(errors, key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(WORK_ITEM_VALIDATION_ERROR, f"{path}{suffix}: {first.message}")


def validate_work_items(root: Path, schema_dir: Path) -> list[str]:
    root = Path(root)
    validated: list[str] = []
    for pattern in ("epics/*.yaml", "sprints/*.yaml", "tickets/*.yaml"):
        for path in sorted(root.glob(pattern)):
            validate_work_item(path, schema_dir)
            validated.append(str(path))
    return validated
