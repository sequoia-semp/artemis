from __future__ import annotations

import hashlib
from pathlib import Path

from pga_workbench.agent_runtime.release_workflow import collect_release_readiness
from pga_workbench.agent_runtime.work_item_loader import load_ticket
from pga_workbench.validation.models import ValidationCheckResult, ValidationReport
from pga_workbench.validation.reports import write_validation_report


ROOT = Path(__file__).resolve().parents[1]


def _snapshot_for_ticket(ticket_id: str) -> list[dict[str, object]]:
    ticket = load_ticket(ROOT / "work", ticket_id)
    snapshot = []
    for relative in ticket.get("affected_files") or []:
        path = ROOT / str(relative)
        snapshot.append(
            {
                "path": str(relative),
                "exists": path.exists(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() and path.is_file() else None,
                "modified_at": path.stat().st_mtime if path.exists() else None,
            }
        )
    return snapshot


def _write_report(tmp_path: Path, *, ticket_id: str = "T-0030", skipped: bool = False, stale: bool = False, strict: bool = True) -> Path:
    snapshot = _snapshot_for_ticket("T-0030")
    if stale and snapshot:
        snapshot[0]["sha256"] = "stale"
    report = ValidationReport(
        report_id="validation.release",
        generated_at="2026-06-05T00:00:00Z",
        repo_root=str(ROOT),
        ticket_id=ticket_id,
        strict=strict,
        overall_status="passed",
        skipped=skipped,
        checks=[
            ValidationCheckResult(
                check_id="pytest",
                label="pytest",
                status="skipped" if skipped else "passed",
                required=True,
                duration_seconds=0.1,
                summary="pytest",
                details={},
            )
        ],
        affected_files_snapshot=snapshot,
    )
    path = tmp_path / "validation.json"
    write_validation_report(report, path)
    return path


def test_missing_validation_report_blocks_readiness(tmp_path: Path):
    result = collect_release_readiness(ROOT, ticket_id="T-0030", validation_report=tmp_path / "missing.json", skip_tests=True)

    assert result["ready_for_release_prep"] is False
    assert any("validation report missing" in blocker for blocker in result["blockers"])


def test_skipped_validation_report_blocks_readiness(tmp_path: Path):
    result = collect_release_readiness(ROOT, ticket_id="T-0030", validation_report=_write_report(tmp_path, skipped=True), skip_tests=True)

    assert result["ready_for_release_prep"] is False
    assert any("skipped" in blocker for blocker in result["blockers"])


def test_ticket_mismatch_blocks_readiness(tmp_path: Path):
    result = collect_release_readiness(ROOT, ticket_id="T-0030", validation_report=_write_report(tmp_path, ticket_id="T-0031"), skip_tests=True)

    assert result["ready_for_release_prep"] is False
    assert any("ticket mismatch" in blocker for blocker in result["blockers"])


def test_stale_snapshot_blocks_readiness(tmp_path: Path):
    result = collect_release_readiness(ROOT, ticket_id="T-0030", validation_report=_write_report(tmp_path, stale=True), skip_tests=True)

    assert result["ready_for_release_prep"] is False
    assert any("changed after validation" in blocker for blocker in result["blockers"])


def test_non_strict_validation_report_blocks_readiness(tmp_path: Path):
    result = collect_release_readiness(ROOT, ticket_id="T-0030", validation_report=_write_report(tmp_path, strict=False), skip_tests=True)

    assert result["ready_for_release_prep"] is False
    assert "validation report was not strict" in result["blockers"]


def test_incomplete_approved_change_request_blocks_readiness(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "pga_workbench.agent_runtime.release_workflow._approved_change_request",
        lambda repo_root, ticket_id: {"path": "development/change_requests/CR-INCOMPLETE.yaml", "change_id": "CR-INCOMPLETE", "approval": {"status": "approved"}},
    )

    result = collect_release_readiness(ROOT, ticket_id="T-0030", validation_report=_write_report(tmp_path), skip_tests=True)

    assert result["ready_for_release_prep"] is False
    assert "approved change request lacks affected_files" in result["blockers"]
    assert "approved change request lacks tests_required" in result["blockers"]
    assert "approved change request lacks rollback_plan" in result["blockers"]
