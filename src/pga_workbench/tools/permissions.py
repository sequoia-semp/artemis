from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..agent.modes import normalize_mode
from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from .registry import load_tool_registry

TOOL_PERMISSION_ERROR = "TOOL_PERMISSION_ERROR"


@dataclass(frozen=True)
class ToolPolicyDecision:
    tool_id: str
    mode: str
    risk: str
    allowed: bool
    approval: str
    can_modify_repo: bool
    requires_ticket: bool
    reason: str


def load_tool_permissions(path: Path, schema_dir: Path) -> dict[str, Any]:
    path = Path(path)
    payload = load_yaml_unique(path)
    if not isinstance(payload, dict):
        raise WorkbenchException(TOOL_PERMISSION_ERROR, f"Tool permissions must be a mapping: {path}")
    schema = load_yaml_unique(Path(schema_dir) / "tool_permissions.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(TOOL_PERMISSION_ERROR, f"{path}{suffix}: {first.message}")
    return payload


def classify_tool(
    tool_id: str,
    tools: dict[str, Any],
    permissions: dict[str, Any],
    mode: str,
    ticket: str | None = None,
) -> ToolPolicyDecision:
    mode_name = normalize_mode(mode).value
    tool = (tools.get("tools") or {}).get(tool_id)
    if not isinstance(tool, dict):
        raise WorkbenchException(TOOL_PERMISSION_ERROR, f"Unknown tool: {tool_id}")
    risk = str(tool.get("risk"))
    risk_policy = (permissions.get("risk_levels") or {}).get(risk)
    if not isinstance(risk_policy, dict):
        raise WorkbenchException(TOOL_PERMISSION_ERROR, f"Unknown risk level for {tool_id}: {risk}")
    mode_policy = (permissions.get("mode_policy") or {}).get(mode_name) or {}
    allowed_risks = set(mode_policy.get("allowed_risks") or [])
    forbidden_risks = set(mode_policy.get("forbidden_risks") or [])
    requires_ticket = bool(risk_policy.get("requires_ticket"))

    allowed = risk in allowed_risks and risk not in forbidden_risks
    reason = "allowed"
    if not allowed:
        reason = f"risk {risk} is not allowed in {mode_name} mode"
    elif requires_ticket and not ticket:
        allowed = False
        reason = f"risk {risk} requires a ticket"

    return ToolPolicyDecision(
        tool_id=tool_id,
        mode=mode_name,
        risk=risk,
        allowed=allowed,
        approval=str(risk_policy.get("approval")),
        can_modify_repo=bool(risk_policy.get("can_modify_repo")),
        requires_ticket=requires_ticket,
        reason=reason,
    )


def assert_tool_allowed(
    tool_id: str,
    mode: str,
    ticket_id: str | None = None,
    approval_context: dict[str, Any] | None = None,
    *,
    repo_root: Path | None = None,
    tools: dict[str, Any] | None = None,
    permissions: dict[str, Any] | None = None,
) -> ToolPolicyDecision:
    """Fail closed when a tool is not executable in the requested mode."""
    root = Path(repo_root or ".")
    registry = tools or load_tool_registry(root / "registries" / "tools.yaml", root / "schemas")
    policy = permissions or load_tool_permissions(root / "registries" / "tool_permissions.yaml", root / "schemas")
    decision = classify_tool(tool_id, registry, policy, mode, ticket=ticket_id)
    if not decision.allowed:
        raise WorkbenchException(TOOL_PERMISSION_ERROR, decision.reason)

    context = approval_context or {}
    if decision.can_modify_repo and not ticket_id:
        raise WorkbenchException(TOOL_PERMISSION_ERROR, f"{tool_id} requires a ticket before repo mutation")
    if decision.risk == "release_candidate" and not context.get("validation_passed"):
        raise WorkbenchException(TOOL_PERMISSION_ERROR, f"{tool_id} requires passed native validation")
    if context.get("convention_change") and not context.get("approved_change_request"):
        raise WorkbenchException(TOOL_PERMISSION_ERROR, f"{tool_id} requires an approved change request for convention changes")
    return decision


def summarize_tool_policy(tools: dict[str, Any], permissions: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for tool_id in sorted((tools.get("tools") or {})):
        tool = tools["tools"][tool_id]
        risk = tool["risk"]
        risk_policy = (permissions.get("risk_levels") or {}).get(risk) or {}
        summary[tool_id] = {
            "risk": risk,
            "modes": tool.get("modes") or [],
            "approval": risk_policy.get("approval"),
            "can_modify_repo": bool(risk_policy.get("can_modify_repo")),
            "requires_ticket": bool(risk_policy.get("requires_ticket")),
        }
    return summary
