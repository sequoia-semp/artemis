from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from ..exceptions import WorkbenchException
from .models import ValidationReport

VALIDATION_REPORT_ERROR = "VALIDATION_REPORT_ERROR"


def write_validation_report(report: ValidationReport, output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def read_validation_report(path: Path) -> ValidationReport:
    path = Path(path)
    if not path.exists():
        raise WorkbenchException(VALIDATION_REPORT_ERROR, f"Validation report missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WorkbenchException(VALIDATION_REPORT_ERROR, f"Validation report must be a JSON object: {path}")
    return ValidationReport.from_dict(payload)


def summarize_validation_report(report: ValidationReport) -> dict[str, Any]:
    return {
        "report_id": report.report_id,
        "ticket_id": report.ticket_id,
        "generated_at": report.generated_at,
        "strict": report.strict,
        "overall_status": report.overall_status,
        "skipped": report.skipped,
        "checks": [
            {
                "check_id": item.check_id,
                "status": item.status,
                "required": item.required,
                "summary": item.summary,
            }
            for item in report.checks
        ],
        "warnings": list(report.warnings),
        "errors": list(report.errors),
    }


def render_regression_markdown(report: ValidationReport) -> str:
    title = report.ticket_id or report.report_id
    lines = [
        f"# Regression Report: {title}",
        "",
        f"Generated At: {report.generated_at}",
        f"Validation Status: {report.overall_status}",
        f"Strict Mode: {report.strict}",
        f"Ticket: {report.ticket_id or 'none'}",
        "Commit / Branch Snapshot:",
        f"- Branch: {report.branch or 'unknown'}",
        f"- Commit: {report.commit or 'unknown'}",
        "",
        "Checks:",
    ]
    for check in report.checks:
        lines.append(f"- {check.check_id}: {check.status} ({check.summary})")
    lines.extend(["", "Command Results:"])
    if report.command_results:
        for result in report.command_results:
            evidence = ""
            combined = "\n".join([result.stdout or "", result.stderr or ""])
            match = re.search(r"(\d+\s+passed(?:,\s+\d+\s+\w+)*)", combined)
            if match:
                evidence = f" - {match.group(1)}"
            lines.append(f"- {result.command}: {result.status}{evidence}")
    else:
        lines.append("- none")
    lines.extend(["", "Warnings:"])
    lines.extend([f"- {item}" for item in report.warnings] or ["- none"])
    lines.extend(["", "Errors:"])
    lines.extend([f"- {item}" for item in report.errors] or ["- none"])
    lines.extend(["", "Known Limitations:"])
    if report.skipped:
        lines.append("- One or more validation checks were skipped; do not treat skipped checks as passed.")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)
