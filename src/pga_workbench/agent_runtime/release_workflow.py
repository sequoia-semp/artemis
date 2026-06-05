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


def collect_release_readiness(repo_root: Path, ticket_id: str | None = None, skip_tests: bool = False) -> dict[str, Any]:
    repo_root = Path(repo_root)
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
    ready = bool(doctor.get("passed")) and validation_passed and all(planning_bridge.values())

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
        "validation_commands": validation_commands,
        "validation_results": validation_results,
        "validation_skipped": validation_skipped,
        "validation_passed": validation_passed,
        "doctor": doctor,
        "ready_for_release_prep": ready,
    }
