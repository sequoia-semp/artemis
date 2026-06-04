from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.agent_runtime.work_item_loader import (
    WORK_ITEM_NOT_FOUND,
    find_ticket,
    load_ticket,
    validate_work_items,
)
from pga_workbench.exceptions import WorkbenchException


ROOT = Path(__file__).resolve().parents[1]


def test_can_load_ticket_yaml():
    ticket = load_ticket(ROOT / "work", "T-0001")
    assert ticket["id"] == "T-0001"
    assert ticket["type"] == "ticket"
    assert ticket["status"] == "done"
    assert "python -m pytest -q" in ticket["required_tests"]
    assert "pga validate-registries" in ticket["required_tests"]


def test_missing_ticket_fails_closed():
    with pytest.raises(WorkbenchException) as exc:
        find_ticket(ROOT / "work", "T-9999")
    assert exc.value.code == WORK_ITEM_NOT_FOUND


def test_required_common_fields_exist_for_initial_work_items():
    import yaml

    required = {"id", "type", "status", "title", "risk"}
    for pattern in ("epics/*.yaml", "sprints/*.yaml", "tickets/*.yaml"):
        for path in sorted((ROOT / "work").glob(pattern)):
            item = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert required <= set(item), path


def test_validate_work_items():
    validated = validate_work_items(ROOT / "work", ROOT / "schemas")
    assert any(path.endswith("T-0001-merge-existing-branch.yaml") for path in validated)
    assert any(path.endswith("T-0017-release-spec-integration.yaml") for path in validated)
    assert len(validated) >= 19
