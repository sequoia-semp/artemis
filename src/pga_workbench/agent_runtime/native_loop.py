from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..core.time import utc_now_iso
from ..dev.coding_backend import load_coding_backend_descriptors
from ..dev.patch_context import collect_development_context
from ..exceptions import WorkbenchException
from ..serialization import write_json
from ..validation.reports import write_validation_report
from ..validation.runner import run_validation
from .release_workflow import collect_release_readiness
from .work_item_loader import load_ticket

NATIVE_LOOP_ERROR = "NATIVE_LOOP_ERROR"


def _loop_report_path(repo_root: Path, ticket_id: str, generated_at: str) -> tuple[Path, Path]:
    safe = generated_at.replace(":", "").replace("-", "")
    root = repo_root / "development" / "agent_runs" / ticket_id
    return root / f"{safe}_loop.json", root / "latest.json"


def _validation_output_path(repo_root: Path, ticket_id: str, generated_at: str) -> tuple[Path, Path]:
    safe = generated_at.replace(":", "").replace("-", "")
    root = repo_root / "development" / "validation_reports" / ticket_id
    return root / f"{safe}_validation.json", root / "latest.json"


def _backend_command(backend: str, ticket_id: str, context_path: Path, instruction: str | None) -> str | None:
    if backend in {"manual", "human"}:
        return None
    if backend == "opencode":
        suffix = f" {instruction}" if instruction else f" Implement {ticket_id} using {context_path}"
        return f"opencode run{suffix}"
    return None


def _reject_forbidden_command(command: str | None, descriptor: dict[str, Any]) -> None:
    if not command:
        return
    forbidden = [str(item).lower() for item in ((descriptor.get("permissions") or {}).get("forbidden") or [])]
    lowered = command.lower()
    hard_forbidden = ["git push", "git tag", "build-state-pack --publish"]
    for item in [*forbidden, *hard_forbidden]:
        pattern = item.replace(" without review", "").replace("approval_required", "").strip()
        if pattern and pattern in lowered:
            raise WorkbenchException(NATIVE_LOOP_ERROR, f"Backend command is forbidden: {command}")


def run_native_agent_loop(
    repo_root: Path,
    ticket_id: str,
    *,
    backend: str = "manual",
    instruction: str | None = None,
    dry_run: bool = False,
    run_backend: bool = False,
    output: Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    ticket = load_ticket(repo_root / "work", ticket_id)
    if ticket.get("status") != "active":
        raise WorkbenchException(NATIVE_LOOP_ERROR, f"Agent loop requires active ticket: {ticket_id} is {ticket.get('status')}")
    backend_key = "human" if backend == "manual" else backend
    descriptors = load_coding_backend_descriptors(repo_root / "integrations" / "coding_backends")
    descriptor = descriptors.get(backend_key)
    if descriptor is None:
        raise WorkbenchException(NATIVE_LOOP_ERROR, f"Unknown coding backend: {backend}")
    if backend_key == "opencode" and shutil.which("opencode") is None and not dry_run:
        raise WorkbenchException(NATIVE_LOOP_ERROR, "opencode backend is not installed")

    generated_at = utc_now_iso()
    context_path = output or Path(tempfile.gettempdir()) / f"artemis_{ticket_id}_context.json"
    context = collect_development_context(repo_root, ticket_id)
    write_json(context_path, context)
    command = _backend_command(backend, ticket_id, context_path, instruction)
    _reject_forbidden_command(command, descriptor)

    validation_report_path = None
    release_check = None
    warnings: list[str] = []
    errors: list[str] = []
    backend_ran = False
    if command and run_backend and not dry_run:
        raise WorkbenchException(NATIVE_LOOP_ERROR, "Backend execution is intentionally not automatic in Sprint 1")
    if not dry_run:
        validation = run_validation(repo_root, ticket_id=ticket_id, strict=False)
        dated, latest = _validation_output_path(repo_root, ticket_id, generated_at)
        write_validation_report(validation, dated)
        write_validation_report(validation, latest)
        validation_report_path = str(latest.relative_to(repo_root))
        release_check = collect_release_readiness(repo_root, ticket_id=ticket_id, validation_report=latest)
        if validation.overall_status != "passed":
            errors.extend(validation.errors)
    else:
        warnings.append("dry-run: backend, validation, and release check were not run")

    report = {
        "ticket_id": ticket_id,
        "backend": backend,
        "context_path": str(context_path),
        "backend_command": command,
        "backend_ran": backend_ran,
        "validation_report": validation_report_path,
        "release_check": release_check,
        "warnings": warnings,
        "errors": errors,
    }
    dated_loop, latest_loop = _loop_report_path(repo_root, ticket_id, generated_at)
    write_json(dated_loop, report)
    write_json(latest_loop, report)
    return report
