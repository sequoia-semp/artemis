from __future__ import annotations

from pathlib import Path

from pga_workbench.cli import artemis_main, build_artemis_parser
from pga_workbench.validation.models import ValidationCheckResult, ValidationReport


def _report() -> ValidationReport:
    return ValidationReport(
        report_id="validation.cli",
        generated_at="2026-06-05T00:00:00Z",
        repo_root="/tmp/repo",
        ticket_id="T-0030",
        strict=False,
        overall_status="passed",
        skipped=False,
        checks=[
            ValidationCheckResult(
                check_id="pytest",
                label="pytest",
                status="passed",
                required=True,
                duration_seconds=0.1,
                summary="pytest passed",
                details={},
            )
        ],
    )


def test_artemis_validate_parser_accepts_native_options():
    parser = build_artemis_parser()
    args = parser.parse_args(["validate", "--strict", "--ticket", "T-0030", "--json"])

    assert args.func.__name__ == "_cmd_validate"
    assert args.strict is True
    assert args.ticket == "T-0030"


def test_artemis_validate_cli_writes_output(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("pga_workbench.cli.run_validation", lambda repo_root, ticket_id=None, strict=False: _report())
    output = tmp_path / "validation.json"

    assert artemis_main(["validate", "--ticket", "T-0030", "--output", str(output)]) == 0
    assert output.exists()


def test_artemis_validate_report_cli_writes_markdown(tmp_path: Path):
    from pga_workbench.validation.reports import write_validation_report

    report_path = tmp_path / "validation.json"
    markdown_path = tmp_path / "regression.md"
    write_validation_report(_report(), report_path)

    assert artemis_main(["validate", "report", "--input", str(report_path), "--markdown", str(markdown_path)]) == 0
    assert "# Regression Report: T-0030" in markdown_path.read_text(encoding="utf-8")
