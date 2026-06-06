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
    parse_period = tools["tools"]["parse_period"]
    work_context = tools["tools"]["work_context"]
    release_candidate = tools["tools"]["release_candidate"]
    event_plan = tools["tools"]["pjm_operational_event_candidate_plan"]
    source_audit = tools["tools"]["power_system_source_audit"]

    assert parse_period["authority"] == "deterministic_service"
    assert parse_period["deterministic_service"] is True
    assert parse_period["lineage"]["records"]
    assert event_plan["risk"] == "read_only"
    assert event_plan["authority"] == "deterministic_service"
    assert event_plan["output_contract"]["type"] == "power_system_operational_event_plan"
    assert source_audit["risk"] == "read_only"
    assert source_audit["authority"] == "deterministic_service"
    assert source_audit["input_contract"]["type"] == "power_system_artifact_bundle"
    assert source_audit["output_contract"]["type"] == "power_system_source_audit"
    assert work_context["authority"] == "compatibility_alias"
    assert work_context["output_contract"]["type"] == "artemis_development_context"
    assert repo_patch["adapter"] == "cli"
    assert repo_patch["authority"] == "candidate_only"
    assert repo_patch["deterministic_service"] is False
    assert repo_patch["input_contract"]["type"] == "ticket_id"
    assert release_candidate["authority"] == "human_review_required"
    assert release_candidate["risk"] == "release_candidate"


def test_pjm_operational_event_candidate_plan_tool_is_read_only_for_analysts():
    tools = load_tool_registry(ROOT / "registries/tools.yaml", ROOT / "schemas")
    permissions = load_tool_permissions(ROOT / "registries/tool_permissions.yaml", ROOT / "schemas")

    decision = classify_tool("pjm_operational_event_candidate_plan", tools, permissions, "analyst")

    assert decision.allowed is True
    assert decision.risk == "read_only"


def test_power_system_source_audit_tool_is_read_only_for_analysts():
    tools = load_tool_registry(ROOT / "registries/tools.yaml", ROOT / "schemas")
    permissions = load_tool_permissions(ROOT / "registries/tool_permissions.yaml", ROOT / "schemas")

    decision = classify_tool("power_system_source_audit", tools, permissions, "analyst")

    assert decision.allowed is True
    assert decision.risk == "read_only"
