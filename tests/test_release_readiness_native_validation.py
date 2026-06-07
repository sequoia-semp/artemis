from __future__ import annotations

import hashlib
from pathlib import Path

from pga_workbench.agent_runtime.release_workflow import collect_release_readiness
from pga_workbench.agent_runtime.work_item_loader import load_ticket
from pga_workbench.models import RunManifest
from pga_workbench.validation.models import ValidationCheckResult, ValidationReport
from pga_workbench.validation.reports import write_validation_report


ROOT = Path(__file__).resolve().parents[1]


def test_run_manifest_records_default_provider_provenance():
    manifest = RunManifest(run_id="state-1", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")

    assert manifest.provider == {
        "profile": "deterministic_only",
        "kind": "deterministic_only",
        "model_calls": False,
        "parameters": {},
    }


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


def _write_report(tmp_path: Path, *, ticket_id: str = "T-0030", skipped: bool = False, stale: bool = False, strict: bool = True, context_audit_status: str = "passed") -> Path:
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
            ),
            ValidationCheckResult(
                check_id="context_audit",
                label="context audit",
                status=context_audit_status,
                required=True,
                duration_seconds=0.1,
                summary="context audit",
                details={},
            )
        ],
        affected_files_snapshot=snapshot,
    )
    path = tmp_path / "validation.json"
    write_validation_report(report, path)
    return path


def _write_report_for_files(tmp_path: Path, ticket_id: str, files: list[str], *, checks: list[str] | None = None) -> Path:
    check_ids = checks or ["pytest", "registries", "capabilities", "context_audit"]
    snapshot = []
    for relative in files:
        path = ROOT / relative
        snapshot.append(
            {
                "path": relative,
                "exists": path.exists(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() and path.is_file() else None,
                "modified_at": path.stat().st_mtime if path.exists() else None,
            }
        )
    report = ValidationReport(
        report_id=f"validation.{ticket_id}",
        generated_at="2026-06-05T00:00:00Z",
        repo_root=str(ROOT),
        ticket_id=ticket_id,
        strict=True,
        overall_status="passed",
        skipped=False,
        checks=[
            ValidationCheckResult(
                check_id=check_id,
                label=check_id,
                status="passed",
                required=True,
                duration_seconds=0.1,
                summary=check_id,
                details={},
            )
            for check_id in check_ids
        ],
        affected_files_snapshot=snapshot,
    )
    path = tmp_path / f"{ticket_id}_validation.json"
    write_validation_report(report, path)
    return path


def _ticket(ticket_id: str, files: list[str], *, context_profile: str | None = None, required_tests: list[str] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": ticket_id,
        "type": "ticket",
        "status": "validated",
        "title": "Fixture ticket",
        "risk": "high",
        "affected_files": files,
        "required_tests": required_tests or ["python -m pytest tests/test_fixture.py -q"],
        "change_request_required": False,
        "validation_report": f"development/validation_reports/{ticket_id}/latest.json",
        "regression_report": f"development/regression_reports/REGRESSION_REPORT_{ticket_id}.md",
    }
    if context_profile is not None:
        payload["context_profile"] = context_profile
    return payload


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


def test_failed_context_audit_blocks_readiness(tmp_path: Path):
    result = collect_release_readiness(ROOT, ticket_id="T-0030", validation_report=_write_report(tmp_path, context_audit_status="failed"), skip_tests=True)

    assert result["ready_for_release_prep"] is False
    assert "validation report lacks passed context_audit evidence" in result["blockers"]


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


def test_validation_report_must_cover_ticket_affected_files(monkeypatch, tmp_path: Path):
    ticket = _ticket("T-FIXTURE", ["README.md", "docs/README.md"])
    monkeypatch.setattr("pga_workbench.agent_runtime.release_workflow.load_ticket", lambda repo_root, ticket_id: ticket)

    result = collect_release_readiness(ROOT, ticket_id="T-FIXTURE", validation_report=_write_report_for_files(tmp_path, "T-FIXTURE", ["README.md"]), skip_tests=True)

    assert result["ready_for_release_prep"] is False
    assert any("lacks ticket affected-file snapshots" in blocker for blocker in result["blockers"])


def test_semantic_changes_require_trading_or_behavioral_context_profile(monkeypatch, tmp_path: Path):
    files = ["src/pga_workbench/services/pnl.py"]
    ticket = _ticket("T-SEMANTIC", files, context_profile="wrapper")
    monkeypatch.setattr("pga_workbench.agent_runtime.release_workflow.load_ticket", lambda repo_root, ticket_id: ticket)

    result = collect_release_readiness(ROOT, ticket_id="T-SEMANTIC", validation_report=_write_report_for_files(tmp_path, "T-SEMANTIC", files), skip_tests=True)

    assert result["semantic_change"]["is_semantic_change"] is True
    assert any("semantic changes require context_profile" in blocker for blocker in result["blockers"])


def test_semantic_changes_require_strict_schema_and_lineage_checks(monkeypatch, tmp_path: Path):
    files = ["src/pga_workbench/services/normalization.py"]
    ticket = _ticket("T-SEMANTIC-CHECKS", files, context_profile="behavioral")
    monkeypatch.setattr("pga_workbench.agent_runtime.release_workflow.load_ticket", lambda repo_root, ticket_id: ticket)

    result = collect_release_readiness(
        ROOT,
        ticket_id="T-SEMANTIC-CHECKS",
        validation_report=_write_report_for_files(tmp_path, "T-SEMANTIC-CHECKS", files, checks=["pytest", "context_audit"]),
        skip_tests=True,
    )

    assert any("semantic changes require passed validation check: registries" in blocker for blocker in result["blockers"])
    assert any("semantic changes require passed validation check: capabilities" in blocker for blocker in result["blockers"])


def test_convention_sensitive_semantic_changes_require_approved_cr(monkeypatch, tmp_path: Path):
    files = ["registries/quoted_spreads.yaml"]
    ticket = _ticket("T-CONVENTION", files, context_profile="trading_domain")
    monkeypatch.setattr("pga_workbench.agent_runtime.release_workflow.load_ticket", lambda repo_root, ticket_id: ticket)

    result = collect_release_readiness(ROOT, ticket_id="T-CONVENTION", validation_report=_write_report_for_files(tmp_path, "T-CONVENTION", files), skip_tests=True)

    assert result["semantic_change"]["convention_sensitive_files"] == files
    assert "convention-sensitive semantic changes require approved change request metadata" in result["blockers"]


def test_convention_sensitive_semantic_changes_accept_approved_cr_metadata(monkeypatch, tmp_path: Path):
    files = ["registries/quoted_spreads.yaml"]
    ticket = _ticket("T-CONVENTION-APPROVED", files, context_profile="trading_domain")
    monkeypatch.setattr("pga_workbench.agent_runtime.release_workflow.load_ticket", lambda repo_root, ticket_id: ticket)
    monkeypatch.setattr(
        "pga_workbench.agent_runtime.release_workflow._approved_change_request",
        lambda repo_root, ticket_id: {
            "path": "development/change_requests/CR-FIXTURE.yaml",
            "change_id": "CR-FIXTURE",
            "approval": {"status": "approved"},
            "affected_files": files,
            "tests_required": ["python -m pytest tests/test_power_basis.py -q"],
            "rollback_plan": "Revert fixture changes.",
        },
    )

    result = collect_release_readiness(ROOT, ticket_id="T-CONVENTION-APPROVED", validation_report=_write_report_for_files(tmp_path, "T-CONVENTION-APPROVED", files), skip_tests=True)

    assert result["semantic_change"]["convention_sensitive_files"] == files
    assert not any("convention-sensitive semantic changes require approved change request metadata" in blocker for blocker in result["blockers"])
