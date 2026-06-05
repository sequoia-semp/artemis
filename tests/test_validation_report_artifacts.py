from __future__ import annotations

from pathlib import Path

from pga_workbench.validation.models import ValidationCheckResult, ValidationReport
from pga_workbench.validation.reports import (
    read_validation_report,
    render_regression_markdown,
    summarize_validation_report,
    write_validation_report,
)


def _report(status: str = "passed", skipped: bool = False) -> ValidationReport:
    return ValidationReport(
        report_id="validation.test",
        generated_at="2026-06-05T00:00:00Z",
        repo_root="/tmp/repo",
        ticket_id="T-0030",
        strict=True,
        overall_status=status,  # type: ignore[arg-type]
        skipped=skipped,
        checks=[
            ValidationCheckResult(
                check_id="pytest",
                label="pytest",
                status="skipped" if skipped else "passed",
                required=True,
                duration_seconds=0.1,
                summary="pytest skipped" if skipped else "pytest passed",
                details={},
            )
        ],
        changed_files_snapshot=[],
        command_results=[],
        warnings=[],
        errors=[] if status == "passed" else ["pytest: failed"],
        affected_files_snapshot=[],
        branch="main",
        commit="abc123",
    )


def test_validation_report_json_round_trips(tmp_path: Path):
    path = tmp_path / "report.json"
    write_validation_report(_report(), path)

    loaded = read_validation_report(path)

    assert loaded.ticket_id == "T-0030"
    assert loaded.checks[0].check_id == "pytest"
    assert loaded.to_dict() == _report().to_dict()


def test_markdown_report_renders_required_sections():
    markdown = render_regression_markdown(_report(skipped=True))

    assert "# Regression Report: T-0030" in markdown
    assert "Generated At:" in markdown
    assert "Validation Status:" in markdown
    assert "Strict Mode:" in markdown
    assert "Commit / Branch Snapshot:" in markdown
    assert "Warnings:" in markdown
    assert "Known Limitations:" in markdown
    assert "pytest: skipped" in markdown


def test_summary_keeps_skipped_as_skipped():
    summary = summarize_validation_report(_report(skipped=True))

    assert summary["checks"][0]["status"] == "skipped"
