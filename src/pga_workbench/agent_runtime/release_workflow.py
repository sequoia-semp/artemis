from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - package metadata now requires Python 3.11+.
    tomllib = None

from .capabilities import collect_agent_doctor
from .work_item_loader import load_ticket


def _load_pyproject(repo_root: Path) -> dict[str, Any]:
    if tomllib is None:
        return {}
    with (repo_root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _regression_report_summary(repo_root: Path) -> dict[str, Any]:
    report = repo_root / "development" / "regression_reports" / "REGRESSION_REPORT_v0.1.md"
    if not report.exists():
        return {"path": str(report), "exists": False, "test_count": None}
    text = report.read_text(encoding="utf-8")
    match = re.search(r"(\d+)\s+passed", text)
    return {
        "path": str(report.relative_to(repo_root)),
        "exists": True,
        "test_count": int(match.group(1)) if match else None,
    }


def collect_release_readiness(repo_root: Path, ticket_id: str | None = None, skip_tests: bool = False) -> dict[str, Any]:
    repo_root = Path(repo_root)
    pyproject = _load_pyproject(repo_root)
    project = pyproject.get("project") or {}
    doctor = collect_agent_doctor(repo_root, skip_tests=skip_tests)
    planning_bridge = {
        "pjm_workbench_mvp_agent_spec.md": (repo_root / "pjm_workbench_mvp_agent_spec.md").exists(),
        "pjm_workbench_mvp_backlog.yaml": (repo_root / "pjm_workbench_mvp_backlog.yaml").exists(),
    }
    ticket = load_ticket(repo_root / "work", ticket_id) if ticket_id else None
    required_note_fields = [
        "package version",
        "convention version or unchanged statement",
        "schema changes",
        "registry changes",
        "tests run",
        "known gaps",
    ]
    ready = bool(doctor.get("passed")) and all(planning_bridge.values())

    return {
        "package": {
            "name": project.get("name"),
            "version": project.get("version"),
            "requires_python": project.get("requires-python"),
        },
        "ticket": ticket,
        "planning_bridge": planning_bridge,
        "regression_report": _regression_report_summary(repo_root),
        "required_release_note_fields": required_note_fields,
        "validation_passed": bool(doctor.get("passed")),
        "doctor": doctor,
        "ready_for_release_prep": ready,
    }
