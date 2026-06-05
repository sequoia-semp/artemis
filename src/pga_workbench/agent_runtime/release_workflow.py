from __future__ import annotations

from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - package metadata now requires Python 3.11+.
    tomllib = None

from .capabilities import collect_agent_doctor
from .work_item_loader import load_ticket
from ..registry import load_yaml_unique
from ..validation.reports import read_validation_report

LOCKED_CONVENTION_PREFIXES = (
    "domain/",
    "docs/CONVENTIONS_LOCKED_v0.1.md",
)


def _load_pyproject(repo_root: Path) -> dict[str, Any]:
    if tomllib is None:
        return {}
    with (repo_root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _regression_report_summary(repo_root: Path, path: str | None = None) -> dict[str, Any]:
    report = repo_root / (path or "development/regression_reports/REGRESSION_REPORT_v0.1.md")
    if not report.exists():
        return {"path": str(report), "exists": False, "test_count": None}
    text = report.read_text(encoding="utf-8")
    match = re.search(r"(\d+)\s+passed", text)
    return {
        "path": str(report.relative_to(repo_root)),
        "exists": True,
        "test_count": int(match.group(1)) if match else None,
    }


def _release_validation_commands(repo_root: Path) -> list[str]:
    config_path = repo_root / "artemis.yaml"
    if not config_path.exists():
        return [
            "python -m pytest -q",
            "pga validate-registries",
            "pga validate-work-items",
            "pga validate-kb",
        ]
    config = load_yaml_unique(config_path)
    return list(((config.get("release") or {}).get("validation_commands") or []))


def _resolve_command(repo_root: Path, command: str) -> list[str]:
    parts = shlex.split(command)
    if not parts:
        return []
    executable = parts[0]
    if executable == "python":
        parts[0] = sys.executable
    elif executable in {"pga", "artemis"}:
        venv_executable = repo_root / ".venv" / "bin" / executable
        parts[0] = str(venv_executable if venv_executable.exists() else shutil.which(executable) or executable)
    return parts


def _run_release_validation_commands(repo_root: Path, commands: list[str], skip_tests: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in commands:
        if skip_tests:
            results.append({"command": command, "passed": False, "skipped": True, "returncode": None})
            continue
        resolved = _resolve_command(repo_root, command)
        completed = subprocess.run(resolved, cwd=repo_root, capture_output=True, text=True)
        results.append(
            {
                "command": command,
                "resolved_command": " ".join(resolved),
                "passed": completed.returncode == 0,
                "skipped": False,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
    return results


def _file_sha256(path: Path) -> str | None:
    import hashlib

    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _approved_change_request(repo_root: Path, ticket_id: str) -> dict[str, Any] | None:
    for path in sorted((repo_root / "development" / "change_requests").glob("*.yaml")):
        payload = load_yaml_unique(path)
        if not isinstance(payload, dict):
            continue
        ticket_ids = {str(item) for item in payload.get("tickets") or []}
        text = "\n".join(str(payload.get(field) or "") for field in ["change_id", "title", "problem_statement"])
        if ticket_id not in ticket_ids and ticket_id not in text:
            continue
        approval = payload.get("approval") or {}
        if approval.get("status") == "approved":
            return {
                "path": str(path.relative_to(repo_root)),
                "change_id": payload.get("change_id"),
                "approval": approval,
                "affected_files": list(payload.get("affected_files") or []),
                "tests_required": list(payload.get("tests_required") or []),
                "rollback_plan": payload.get("rollback_plan"),
            }
    return None


def _locked_convention_files(ticket: dict[str, Any] | None) -> list[str]:
    locked = []
    for item in (ticket or {}).get("affected_files") or []:
        path = str(item)
        if path.startswith(LOCKED_CONVENTION_PREFIXES):
            locked.append(path)
    return locked


def _change_request_blockers(ticket: dict[str, Any] | None, change_request: dict[str, Any] | None) -> list[str]:
    if not ticket:
        return []
    blockers = []
    if change_request is None:
        return ["approved change request is missing"]

    cr_files = {str(item).rstrip("/") for item in change_request.get("affected_files") or []}
    ticket_files = {str(item) for item in ticket.get("affected_files") or []}
    if not cr_files:
        blockers.append("approved change request lacks affected_files")
    elif not any(any(ticket_file == cr_file or ticket_file.startswith(f"{cr_file}/") for cr_file in cr_files) for ticket_file in ticket_files):
        blockers.append("approved change request affected_files do not overlap ticket affected_files")

    if not change_request.get("tests_required"):
        blockers.append("approved change request lacks tests_required")
    if not change_request.get("rollback_plan"):
        blockers.append("approved change request lacks rollback_plan")
    return blockers


def _default_validation_report_path(repo_root: Path, ticket_id: str | None, ticket: dict[str, Any] | None) -> Path | None:
    if ticket and ticket.get("validation_report"):
        return repo_root / str(ticket["validation_report"])
    if ticket_id:
        return repo_root / "development" / "validation_reports" / ticket_id / "latest.json"
    return repo_root / "development" / "validation_reports" / "latest.json"


def _native_validation_summary(repo_root: Path, ticket_id: str | None, ticket: dict[str, Any] | None, validation_report_path: Path | None) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    report_payload: dict[str, Any] | None = None
    report_path = validation_report_path or _default_validation_report_path(repo_root, ticket_id, ticket)
    if report_path is None:
        blockers.append("validation report path is unavailable")
        return {"path": None, "exists": False, "report": None, "blockers": blockers, "warnings": warnings}
    report_path = Path(report_path)
    if not report_path.is_absolute():
        report_path = repo_root / report_path
    if not report_path.exists():
        blockers.append(f"validation report missing: {report_path}")
        return {"path": str(report_path.relative_to(repo_root) if report_path.is_relative_to(repo_root) else report_path), "exists": False, "report": None, "blockers": blockers, "warnings": warnings}

    report = read_validation_report(report_path)
    report_payload = report.to_dict()
    if ticket_id and report.ticket_id != ticket_id:
        blockers.append(f"validation report ticket mismatch: expected {ticket_id}, found {report.ticket_id}")
    if report.overall_status != "passed":
        blockers.append(f"validation report did not pass: {report.overall_status}")
    if not report.strict:
        blockers.append("validation report was not strict")
    if report.skipped:
        blockers.append("validation report includes skipped checks")
    for check in report.checks:
        if check.required and check.status in {"skipped", "failed", "error"}:
            blockers.append(f"required validation check {check.check_id} is {check.status}")
    if not any(check.check_id == "context_audit" and check.status == "passed" for check in report.checks):
        blockers.append("validation report lacks passed context_audit evidence")
    if ticket_id and not report.affected_files_snapshot:
        blockers.append("validation report lacks affected file snapshot")
    for item in report.affected_files_snapshot:
        path = repo_root / str(item.get("path"))
        if bool(item.get("exists")) != path.exists():
            blockers.append(f"affected file existence changed after validation: {item.get('path')}")
            continue
        if path.exists() and item.get("sha256") != _file_sha256(path):
            blockers.append(f"affected file changed after validation: {item.get('path')}")
    return {
        "path": str(report_path.relative_to(repo_root) if report_path.is_relative_to(repo_root) else report_path),
        "exists": True,
        "report": report_payload,
        "blockers": blockers,
        "warnings": warnings,
    }


def collect_release_readiness(
    repo_root: Path,
    ticket_id: str | None = None,
    skip_tests: bool = False,
    validation_report: Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    pyproject = _load_pyproject(repo_root)
    project = pyproject.get("project") or {}
    doctor = collect_agent_doctor(repo_root, skip_tests=True)
    validation_commands = _release_validation_commands(repo_root)
    validation_results = _run_release_validation_commands(repo_root, validation_commands, skip_tests=skip_tests)
    planning_bridge = {
        "docs/archive/pjm_workbench_mvp_agent_spec.md": (repo_root / "docs/archive/pjm_workbench_mvp_agent_spec.md").exists(),
        "work/backlog/pjm_workbench_mvp_backlog.yaml": (repo_root / "work/backlog/pjm_workbench_mvp_backlog.yaml").exists(),
    }
    ticket = load_ticket(repo_root / "work", ticket_id) if ticket_id else None
    native_validation = _native_validation_summary(repo_root, ticket_id, ticket, validation_report)
    required_note_fields = [
        "package version",
        "convention version or unchanged statement",
        "schema changes",
        "registry changes",
        "tests run",
        "known gaps",
    ]
    validation_skipped = any(result.get("skipped") for result in validation_results)
    validation_passed = all(result.get("passed") for result in validation_results) and not validation_skipped
    blockers: list[str] = list(native_validation.get("blockers") or [])
    warnings: list[str] = list(native_validation.get("warnings") or [])
    ticket_status = str((ticket or {}).get("status") or "")
    if ticket_id and ticket_status not in {"validated", "closed", "done"}:
        blockers.append(f"ticket lifecycle state is not validated or closed: {ticket_status}")
    locked_convention_files = _locked_convention_files(ticket)
    if ticket and (ticket.get("change_request_required") or locked_convention_files):
        change_request = _approved_change_request(repo_root, ticket_id or "")
        blockers.extend(_change_request_blockers(ticket, change_request))
    else:
        change_request = None
    if locked_convention_files and not (ticket or {}).get("change_request_required"):
        blockers.append("locked convention files require change_request_required=true")
    regression = _regression_report_summary(repo_root, str(ticket.get("regression_report")) if ticket and ticket.get("regression_report") else None)
    if ticket and ticket.get("regression_report") and not regression.get("exists"):
        blockers.append(f"regression report missing: {ticket.get('regression_report')}")
    if skip_tests:
        blockers.append("--skip-tests is a dry-run path and cannot be release-ready")
    if not all(planning_bridge.values()):
        blockers.append("planning bridge files are missing")
    if not doctor.get("passed"):
        blockers.append("agent doctor checks did not pass")
    if not validation_passed:
        warnings.append("compatibility validation commands did not all pass")
    ready = not blockers

    return {
        "package": {
            "name": project.get("name"),
            "version": project.get("version"),
            "requires_python": project.get("requires-python"),
        },
        "ticket": ticket,
        "planning_bridge": planning_bridge,
        "regression_report": regression,
        "native_validation": native_validation,
        "change_request": change_request,
        "locked_convention_files": locked_convention_files,
        "blockers": blockers,
        "warnings": warnings,
        "required_release_note_fields": required_note_fields,
        "validation_commands": validation_commands,
        "validation_results": validation_results,
        "validation_skipped": validation_skipped,
        "validation_passed": validation_passed,
        "doctor": doctor,
        "ready_for_release_prep": ready,
    }
