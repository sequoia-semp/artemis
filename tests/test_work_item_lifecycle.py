from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.agent_runtime.work_item_loader import (
    WORK_ITEM_TRANSITION_ERROR,
    transition_ticket,
    validate_ticket_lifecycle,
)
from pga_workbench.exceptions import WorkbenchException


def test_valid_lifecycle_state_passes():
    validate_ticket_lifecycle(
        {
            "id": "T-TEST",
            "type": "ticket",
            "status": "validated",
            "validated_at": "2026-06-05T00:00:00Z",
            "validation_report": "development/validation_reports/T-TEST/latest.json",
            "regression_report": "development/regression_reports/REGRESSION_REPORT_T-TEST.md",
        }
    )


def test_missing_validated_fields_fail():
    with pytest.raises(WorkbenchException):
        validate_ticket_lifecycle({"id": "T-TEST", "type": "ticket", "status": "validated"})


def test_invalid_transition_fails(tmp_path: Path):
    tickets = tmp_path / "tickets"
    tickets.mkdir()
    (tickets / "T-TEST.yaml").write_text(
        "\n".join(
            [
                "id: T-TEST",
                "type: ticket",
                "status: active",
                "title: Test",
                "risk: low",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(WorkbenchException) as exc:
        transition_ticket(tmp_path, "T-TEST", "closed", timestamp="2026-06-05T00:00:00Z", reviewed_by="user")

    assert exc.value.code == WORK_ITEM_TRANSITION_ERROR
