from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.tools.permissions import assert_tool_allowed, classify_tool, load_tool_permissions
from pga_workbench.tools.registry import load_tool_registry


ROOT = Path(__file__).resolve().parents[1]


def test_analyst_mode_cannot_run_repo_write_tools():
    tools = load_tool_registry(ROOT / "registries/tools.yaml", ROOT / "schemas")
    permissions = load_tool_permissions(ROOT / "registries/tool_permissions.yaml", ROOT / "schemas")

    decision = classify_tool("repo_patch", tools, permissions, "analyst", ticket="T-0018")
    assert decision.allowed is False
    assert "not allowed" in decision.reason


def test_development_repo_write_requires_ticket():
    tools = load_tool_registry(ROOT / "registries/tools.yaml", ROOT / "schemas")
    permissions = load_tool_permissions(ROOT / "registries/tool_permissions.yaml", ROOT / "schemas")

    missing_ticket = classify_tool("repo_patch", tools, permissions, "development")
    with_ticket = classify_tool("repo_patch", tools, permissions, "development", ticket="T-0018")

    assert missing_ticket.allowed is False
    assert missing_ticket.requires_ticket is True
    assert with_ticket.allowed is True


def test_assert_tool_allowed_enforces_runtime_boundaries():
    with pytest.raises(WorkbenchException) as exc:
        assert_tool_allowed("release_candidate", "analyst", ticket_id="T-0018", repo_root=ROOT, approval_context={"validation_passed": True})
    assert "not allowed" in exc.value.message

    with pytest.raises(WorkbenchException) as exc:
        assert_tool_allowed("repo_patch", "development", repo_root=ROOT)
    assert "requires a ticket" in exc.value.message

    with pytest.raises(WorkbenchException) as exc:
        assert_tool_allowed("release_candidate", "development", ticket_id="T-0018", repo_root=ROOT)
    assert "requires passed native validation" in exc.value.message

    decision = assert_tool_allowed("release_candidate", "development", ticket_id="T-0018", repo_root=ROOT, approval_context={"validation_passed": True})
    assert decision.allowed is True


def test_convention_change_requires_approved_change_request_context():
    with pytest.raises(WorkbenchException) as exc:
        assert_tool_allowed(
            "repo_patch",
            "development",
            ticket_id="T-0022",
            repo_root=ROOT,
            approval_context={"convention_change": True},
        )
    assert "approved change request" in exc.value.message


def test_tool_spec_v2_metadata_is_validated_and_exposed():
    tools = load_tool_registry(ROOT / "registries/tools.yaml", ROOT / "schemas")
    repo_patch = tools["tools"]["repo_patch"]

    assert repo_patch["adapter"] == "cli"
    assert repo_patch["authority"] == "candidate_only"
    assert repo_patch["deterministic_service"] is False
    assert repo_patch["input_contract"]["type"] == "ticket_id"
