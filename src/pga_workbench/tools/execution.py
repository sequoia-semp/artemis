from __future__ import annotations

from .permissions import ToolPolicyDecision


def execution_allowed(decision: ToolPolicyDecision) -> bool:
    return decision.allowed
