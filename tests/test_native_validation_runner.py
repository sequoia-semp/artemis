from __future__ import annotations

from pathlib import Path

from pga_workbench.validation.models import CommandResult
from pga_workbench.validation.runner import run_validation


ROOT = Path(__file__).resolve().parents[1]


def test_native_runner_reports_expected_checks(monkeypatch):
    monkeypatch.setattr(
        "pga_workbench.validation.runner._run_command",
        lambda repo_root, command: CommandResult(command=command, returncode=0, status="passed", duration_seconds=0.01),
    )

    report = run_validation(ROOT, ticket_id="T-0030", strict=True)
    check_ids = {item.check_id for item in report.checks}

    assert report.overall_status == "passed"
    assert {
        "pytest",
        "registries",
        "work_items",
        "knowledge_base",
        "artemis_config",
        "skills",
        "views",
        "data_sources",
        "capabilities",
        "context_audit",
        "release_sanity",
    } <= check_ids
    assert report.ticket_id == "T-0030"
    assert report.affected_files_snapshot


def test_failed_check_makes_report_failed(monkeypatch):
    monkeypatch.setattr(
        "pga_workbench.validation.runner._run_command",
        lambda repo_root, command: CommandResult(command=command, returncode=1, status="failed", duration_seconds=0.01),
    )

    report = run_validation(ROOT, ticket_id="T-0030", strict=False)

    assert report.overall_status == "failed"
    assert any("pytest" in error for error in report.errors)
