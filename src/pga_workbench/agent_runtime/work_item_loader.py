from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from ..exceptions import WorkbenchException

WORK_ITEM_NOT_FOUND = "WORK_ITEM_NOT_FOUND"
WORK_ITEM_VALIDATION_ERROR = "WORK_ITEM_VALIDATION_ERROR"
WORK_ITEM_TRANSITION_ERROR = "WORK_ITEM_TRANSITION_ERROR"

LIFECYCLE_STATUSES = {"proposed", "active", "implemented", "validated", "closed", "blocked", "superseded"}
LEGACY_STATUSES = {"planned", "ready", "review", "done", "rejected"}
ALLOWED_TRANSITIONS = {
    ("proposed", "active"),
    ("active", "implemented"),
    ("implemented", "validated"),
    ("validated", "closed"),
    ("active", "blocked"),
    ("blocked", "active"),
    ("proposed", "superseded"),
    ("active", "superseded"),
    ("implemented", "superseded"),
}


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
    if item_type == "ticket":
        validate_ticket_lifecycle(payload, label=str(path))


def validate_ticket_lifecycle(ticket: dict[str, Any], label: str = "ticket") -> None:
    status = str(ticket.get("status"))
    if status in LEGACY_STATUSES:
        return
    if status not in LIFECYCLE_STATUSES:
        raise WorkbenchException(WORK_ITEM_VALIDATION_ERROR, f"{label}: unsupported lifecycle status {status}")
    required_by_status = {
        "implemented": ["implemented_at", "implementation_summary"],
        "validated": ["validated_at", "validation_report", "regression_report"],
        "closed": ["closed_at", "reviewed_by", "review_summary"],
        "blocked": ["blocked_reason"],
        "superseded": ["superseded_by"],
    }
    missing = [field for field in required_by_status.get(status, []) if not ticket.get(field)]
    if missing:
        raise WorkbenchException(WORK_ITEM_VALIDATION_ERROR, f"{label}: missing fields for {status}: {missing}")


def validate_work_items(root: Path, schema_dir: Path) -> list[str]:
    root = Path(root)
    validated: list[str] = []
    for pattern in ("epics/*.yaml", "sprints/*.yaml", "tickets/*.yaml"):
        for path in sorted(root.glob(pattern)):
            validate_work_item(path, schema_dir)
            validated.append(str(path))
    return validated


def list_tickets(root: Path) -> list[dict[str, Any]]:
    tickets = []
    for path in sorted((Path(root) / "tickets").glob("*.yaml")):
        ticket = load_work_item(path)
        ticket["_path"] = str(path)
        tickets.append(ticket)
    return tickets


def transition_ticket(
    root: Path,
    ticket_id: str,
    new_status: str,
    *,
    timestamp: str,
    validation_report: str | None = None,
    regression_report: str | None = None,
    reviewed_by: str | None = None,
    review_summary: str | None = None,
    blocked_reason: str | None = None,
    superseded_by: str | None = None,
) -> dict[str, Any]:
    path = find_ticket(root, ticket_id)
    ticket = load_work_item(path)
    old_status = str(ticket.get("status"))
    if (old_status, new_status) not in ALLOWED_TRANSITIONS:
        raise WorkbenchException(WORK_ITEM_TRANSITION_ERROR, f"Invalid transition: {old_status} -> {new_status}")
    ticket["status"] = new_status
    ticket["updated_at"] = timestamp
    if new_status == "implemented":
        ticket["implemented_at"] = timestamp
        ticket.setdefault("implementation_summary", "Implementation completed; validation pending.")
    elif new_status == "validated":
        if not validation_report or not regression_report:
            raise WorkbenchException(WORK_ITEM_TRANSITION_ERROR, "validated transition requires validation_report and regression_report")
        ticket["validated_at"] = timestamp
        ticket["validation_report"] = validation_report
        ticket["regression_report"] = regression_report
    elif new_status == "closed":
        if not reviewed_by:
            raise WorkbenchException(WORK_ITEM_TRANSITION_ERROR, "closed transition requires reviewed_by")
        ticket["closed_at"] = timestamp
        ticket["reviewed_by"] = reviewed_by
        ticket["review_summary"] = review_summary or "Accepted."
    elif new_status == "blocked":
        if not blocked_reason:
            raise WorkbenchException(WORK_ITEM_TRANSITION_ERROR, "blocked transition requires blocked_reason")
        ticket["blocked_reason"] = blocked_reason
    elif new_status == "superseded":
        if not superseded_by:
            raise WorkbenchException(WORK_ITEM_TRANSITION_ERROR, "superseded transition requires superseded_by")
        ticket["superseded_by"] = superseded_by
    validate_ticket_lifecycle(ticket, label=str(path))
    path.write_text(yaml.safe_dump(ticket, sort_keys=False), encoding="utf-8")
    return ticket
