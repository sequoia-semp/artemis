from __future__ import annotations

from enum import Enum
from typing import Any


class AgentMode(str, Enum):
    ANALYST = "analyst"
    DEVELOPMENT = "development"


def normalize_mode(value: str | AgentMode) -> AgentMode:
    if isinstance(value, AgentMode):
        return value
    return AgentMode(str(value))


def mode_can_modify_repo(config: dict[str, Any], mode: str | AgentMode) -> bool:
    mode_name = normalize_mode(mode).value
    mode_config = (config.get("modes") or {}).get(mode_name) or {}
    return bool(mode_config.get("can_modify_repo"))


def mode_requires_ticket(config: dict[str, Any], mode: str | AgentMode) -> bool:
    mode_name = normalize_mode(mode).value
    mode_config = (config.get("modes") or {}).get(mode_name) or {}
    return bool(mode_config.get("requires_ticket"))
