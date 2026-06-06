from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique

SOURCE_ACCESS_POLICY_ERROR = "SOURCE_ACCESS_POLICY_ERROR"


def load_power_system_source_access_policies(registry_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_yaml_unique(Path(registry_dir) / "power_system_source_access_policies.yaml")
    if not isinstance(data, dict):
        raise WorkbenchException(SOURCE_ACCESS_POLICY_ERROR, "Power system source access policies must be a mapping")
    return {str(key): dict(value) for key, value in data.items() if isinstance(value, dict)}


def source_access_policy_for_surface(registry_dir: Path, access_surface: str) -> dict[str, Any]:
    matches = [
        record
        for record in load_power_system_source_access_policies(registry_dir).values()
        if record.get("access_surface") == access_surface and record.get("status") == "approved_core"
    ]
    if len(matches) != 1:
        raise WorkbenchException(
            SOURCE_ACCESS_POLICY_ERROR,
            f"Expected exactly one approved source access policy for {access_surface}, found {len(matches)}",
        )
    return matches[0]
