from __future__ import annotations

from pathlib import Path

from pga_workbench.tools.permissions import classify_tool, load_tool_permissions
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
