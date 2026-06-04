from __future__ import annotations

from pathlib import Path
import re

from ..core.time import utc_now_iso
from ..exceptions import WorkbenchException
from ..models import AgentMemoryEntry
from ..serialization import read_json, write_json


READ_ONLY_AGENT_ACTIONS = {"retrieve", "explain", "compare", "summarize", "scenario"}
MUTATING_AGENT_ACTION_BLOCKED = "MUTATING_AGENT_ACTION_BLOCKED"


def assert_read_only_action(action: str) -> None:
    if action not in READ_ONLY_AGENT_ACTIONS:
        raise WorkbenchException(MUTATING_AGENT_ACTION_BLOCKED, f"Agent action requires reviewed change control: {action}")


def append_memory_entry(path: Path, entry: AgentMemoryEntry) -> None:
    path = Path(path)
    existing = read_json(path) if path.exists() else []
    existing.append(
        {
            "entry_id": entry.entry_id,
            "created_at": entry.created_at,
            "category": entry.category,
            "summary": entry.summary,
            "provenance": entry.provenance,
            "canonical": entry.canonical,
            "related_change_request": entry.related_change_request,
        }
    )
    write_json(path, existing)


def change_request_path(change_dir: Path, change_id: str) -> Path:
    safe = re.sub(r"[^A-Z0-9_-]", "-", change_id.upper())
    return Path(change_dir) / f"{safe}.yaml"


def draft_change_request(change_dir: Path, change_id: str, title: str, problem_statement: str, change_class: int = 1) -> Path:
    path = change_request_path(change_dir, change_id)
    if path.exists():
        raise WorkbenchException("CHANGE_REQUEST_EXISTS", f"Change request exists: {path}")
    body = (
        f"change_id: {change_id}\n"
        f"title: {title}\n"
        f"created_at: {utc_now_iso()}\n"
        f"change_class: {change_class}\n"
        "severity: medium\n"
        f"problem_statement: {problem_statement}\n"
        "root_cause: pending_review\n"
        "affected_files: []\n"
        "tests_required: []\n"
        "approval:\n"
        "  status: proposed\n"
        "rollback_plan: revert the change request and associated implementation commit\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path
