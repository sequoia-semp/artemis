from __future__ import annotations

import hashlib
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..agent.runtime import collect_artemis_capabilities, validate_artemis_config
from ..agent_runtime.kb_validator import validate_knowledge_base
from ..agent_runtime.context_audit import audit_context_surfaces
from ..agent_runtime.work_item_loader import load_ticket, validate_work_items
from ..analyst.view_engine import validate_view_manifest
from ..core.time import utc_now_iso
from ..data.sources import validate_data_sources
from ..exceptions import WorkbenchException
from ..registry import validate_registries
from ..services.power_system_artifact_products import validate_power_system_artifact_product_references
from ..services.power_system_operators import validate_power_system_operator_references
from ..services.power_system_locations import validate_power_location_source_identity_references
from ..services.power_system_retention import validate_power_system_artifact_retention_references
from ..services.power_system_source_metadata import validate_power_system_source_metadata_references
from ..services.power_system_sources import validate_power_system_source_catalog_references
from ..services.source_query_plans import validate_power_system_source_query_plan_references
from ..services.power_prices import validate_power_system_price_feed_contracts
from ..skills.validator import validate_skill_manifest
from .models import CommandResult, ValidationCheckResult, ValidationReport


def _git(repo_root: Path, args: list[str]) -> str | None:
    completed = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _resolve_command(repo_root: Path, command: str) -> list[str]:
    parts = shlex.split(command)
    if not parts:
        return []
    if parts[0] == "python":
        parts[0] = sys.executable
    elif parts[0] in {"pga", "artemis"}:
        venv_executable = repo_root / ".venv" / "bin" / parts[0]
        parts[0] = str(venv_executable if venv_executable.exists() else shutil.which(parts[0]) or parts[0])
    return parts


def _run_command(repo_root: Path, command: str) -> CommandResult:
    started = time.perf_counter()
    completed = subprocess.run(_resolve_command(repo_root, command), cwd=repo_root, capture_output=True, text=True)
    status = "passed" if completed.returncode == 0 else "failed"
    return CommandResult(
        command=command,
        returncode=completed.returncode,
        status=status,
        duration_seconds=round(time.perf_counter() - started, 6),
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _check(label: str, check_id: str, required: bool, func: Callable[[], dict[str, Any] | None]) -> ValidationCheckResult:
    started = time.perf_counter()
    try:
        details = func() or {}
    except WorkbenchException as exc:
        return ValidationCheckResult(
            check_id=check_id,
            label=label,
            status="failed",
            required=required,
            duration_seconds=round(time.perf_counter() - started, 6),
            summary=f"{exc.code}: {exc.message}",
            details={},
        )
    except Exception as exc:  # pragma: no cover - keeps CLI reports deterministic for unexpected failures.
        return ValidationCheckResult(
            check_id=check_id,
            label=label,
            status="error",
            required=required,
            duration_seconds=round(time.perf_counter() - started, 6),
            summary=str(exc),
            details={},
        )
    return ValidationCheckResult(
        check_id=check_id,
        label=label,
        status="passed",
        required=required,
        duration_seconds=round(time.perf_counter() - started, 6),
        summary=str(details.pop("summary", "passed")),
        details=details,
    )


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _affected_file_snapshot(repo_root: Path, ticket_id: str | None) -> list[dict[str, Any]]:
    if not ticket_id:
        return []
    ticket = load_ticket(repo_root / "work", ticket_id)
    snapshot = []
    for item in ticket.get("affected_files") or []:
        relative_path = str(item)
        path = repo_root / relative_path
        stat = path.stat() if path.exists() else None
        snapshot.append(
            {
                "path": relative_path,
                "exists": path.exists(),
                "sha256": _sha256(path),
                "modified_at": stat.st_mtime if stat else None,
            }
        )
    return snapshot


def _release_sanity(repo_root: Path) -> dict[str, Any]:
    github_workflows = repo_root / ".github" / "workflows"
    config = validate_artemis_config(repo_root)
    commands = list((config.get("release") or {}).get("validation_commands") or [])
    github_commands = [command for command in commands if "github" in command.lower()]
    if github_workflows.exists():
        raise WorkbenchException("VALIDATION_GITHUB_WORKFLOW_FORBIDDEN", "GitHub workflow directory is not allowed as workflow authority")
    if github_commands:
        raise WorkbenchException("VALIDATION_GITHUB_COMMAND_FORBIDDEN", f"Release validation references GitHub: {github_commands}")
    return {"summary": "native release sanity checks passed", "validation_commands": commands}


def _context_audit(repo_root: Path) -> dict[str, Any]:
    result = audit_context_surfaces(repo_root)
    if not result.get("passed"):
        raise WorkbenchException("CONTEXT_AUDIT_FAILED", f"context audit blockers: {result['counts']['blockers']}")
    return {"summary": "context audit passed", **result}


def run_validation(repo_root: Path, ticket_id: str | None = None, strict: bool = False) -> ValidationReport:
    repo_root = Path(repo_root).resolve()
    generated_at = utc_now_iso()
    command_results: list[CommandResult] = []
    checks: list[ValidationCheckResult] = []
    warnings: list[str] = []
    errors: list[str] = []

    pytest_result = _run_command(repo_root, "python -m pytest -q")
    command_results.append(pytest_result)
    checks.append(
        ValidationCheckResult(
            check_id="pytest",
            label="pytest",
            status=pytest_result.status,
            required=True,
            duration_seconds=pytest_result.duration_seconds,
            summary="pytest passed" if pytest_result.status == "passed" else "pytest failed",
            details={"returncode": pytest_result.returncode},
        )
    )
    registry_result = _check(
        "registry validation",
        "registries",
        True,
        lambda: {
            "summary": "registry validation passed",
            **validate_registries(repo_root / "registries", repo_root / "schemas").__dict__,
        },
    )
    checks.append(registry_result)
    for warning in registry_result.details.get("warnings") or []:
        warnings.append(str(warning))
    if strict and registry_result.details.get("warnings"):
        checks[-1] = ValidationCheckResult(
            check_id=registry_result.check_id,
            label=registry_result.label,
            status="failed",
            required=True,
            duration_seconds=registry_result.duration_seconds,
            summary="strict mode rejects registry files without schema handlers",
            details=registry_result.details,
        )

    checks.extend(
        [
            _check("work-item validation", "work_items", True, lambda: {"summary": "work items passed", "validated": validate_work_items(repo_root / "work", repo_root / "schemas")}),
            _check("knowledge-base validation", "knowledge_base", True, lambda: {"summary": "knowledge base passed", **validate_knowledge_base(repo_root / "knowledge_base", repo_root / "schemas")}),
            _check("artemis config validation", "artemis_config", True, lambda: {"summary": "artemis config passed", "name": validate_artemis_config(repo_root).get("name")}),
            _check("skill manifest validation", "skills", True, lambda: {"summary": "skill manifest passed", **validate_skill_manifest(repo_root, repo_root / "schemas")}),
            _check("view manifest validation", "views", True, lambda: {"summary": "view manifest passed", **validate_view_manifest(repo_root, repo_root / "schemas")}),
            _check(
                "power-system reference validation",
                "power_system_references",
                True,
                lambda: {
                    "summary": "power system references passed",
                    "artifact_products": validate_power_system_artifact_product_references(repo_root / "registries"),
                    "artifact_retention": validate_power_system_artifact_retention_references(repo_root / "registries"),
                    "location_source_identity": validate_power_location_source_identity_references(repo_root / "registries"),
                    "operators": validate_power_system_operator_references(repo_root / "registries"),
                    "price_feed_contracts": validate_power_system_price_feed_contracts(repo_root / "registries"),
                    "source_query_plans": validate_power_system_source_query_plan_references(repo_root / "registries"),
                    "source_catalog": validate_power_system_source_catalog_references(repo_root / "registries"),
                    "source_metadata": validate_power_system_source_metadata_references(repo_root / "registries"),
                },
            ),
            _check("data-source descriptor validation", "data_sources", True, lambda: {"summary": "data sources passed", **validate_data_sources(repo_root / "registries" / "data_sources.yaml", repo_root / "schemas")}),
            _check("capability validation", "capabilities", True, lambda: {"summary": "capabilities passed", "recommended_mode": collect_artemis_capabilities(repo_root).get("recommended_mode")}),
            _check("context surface audit", "context_audit", True, lambda: _context_audit(repo_root)),
            _check("release-readiness sanity", "release_sanity", True, lambda: _release_sanity(repo_root)),
        ]
    )

    skipped = any(item.status == "skipped" for item in checks)
    failing = [item for item in checks if item.required and item.status in {"failed", "error"}]
    if strict:
        failing.extend(item for item in checks if item.required and item.status == "skipped")
    for item in failing:
        errors.append(f"{item.check_id}: {item.summary}")
    overall_status = "failed" if failing else "passed"
    report_id = f"validation.{ticket_id or 'repo'}.{generated_at.replace(':', '').replace('-', '')}"
    changed = (_git(repo_root, ["status", "--short"]) or "").splitlines()

    return ValidationReport(
        report_id=report_id,
        generated_at=generated_at,
        repo_root=str(repo_root),
        ticket_id=ticket_id,
        strict=strict,
        overall_status=overall_status,
        skipped=skipped,
        checks=checks,
        changed_files_snapshot=changed,
        command_results=command_results,
        warnings=warnings,
        errors=errors,
        affected_files_snapshot=_affected_file_snapshot(repo_root, ticket_id),
        branch=_git(repo_root, ["branch", "--show-current"]),
        commit=_git(repo_root, ["rev-parse", "HEAD"]),
    )
