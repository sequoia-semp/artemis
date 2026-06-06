from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique

POWER_SYSTEM_LOCATION_ERROR = "POWER_SYSTEM_LOCATION_ERROR"


def load_power_locations(registry_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_yaml_unique(Path(registry_dir) / "power_locations.yaml")
    if not isinstance(data, dict):
        raise WorkbenchException(POWER_SYSTEM_LOCATION_ERROR, "power_locations.yaml must be a mapping")
    return {str(key): dict(value) for key, value in data.items() if isinstance(value, dict)}


def validate_power_location_source_identity_references(registry_dir: Path) -> dict[str, dict[str, Any]]:
    locations = load_power_locations(registry_dir)
    pjm_pnodes: dict[int, str] = {}
    resolved: dict[str, dict[str, Any]] = {}
    for location_id, record in sorted(locations.items()):
        if record.get("commodity") != "power" or record.get("status") != "approved_core":
            continue
        supported_market_runs = [str(item) for item in record.get("supported_market_runs") or []]
        default_market_run = str(record.get("default_market_run") or "")
        if not supported_market_runs:
            raise WorkbenchException(
                POWER_SYSTEM_LOCATION_ERROR,
                f"Approved power location {location_id} must declare supported_market_runs",
            )
        if default_market_run not in supported_market_runs:
            raise WorkbenchException(
                POWER_SYSTEM_LOCATION_ERROR,
                f"Approved power location {location_id} default_market_run is not supported: {default_market_run}",
            )
        if str(record.get("iso_or_ba")) == "PJM":
            pnode_id = _require_positive_int(record.get("pjm_pnode_id"), f"Approved PJM power location {location_id} pjm_pnode_id")
            existing_location = pjm_pnodes.get(pnode_id)
            if existing_location is not None:
                raise WorkbenchException(
                    POWER_SYSTEM_LOCATION_ERROR,
                    f"PJM pnode {pnode_id} maps to multiple approved power locations: {existing_location}, {location_id}",
                )
            pjm_pnodes[pnode_id] = location_id
            pnode_name = _require_nonempty(record.get("pjm_pnode_name"), f"Approved PJM power location {location_id} pjm_pnode_name")
            pnode_type = _require_nonempty(record.get("pjm_pnode_type"), f"Approved PJM power location {location_id} pjm_pnode_type")
            source_status = str(record.get("pnode_source_status") or "")
            if source_status != "official_pjm_data_miner_verified":
                raise WorkbenchException(
                    POWER_SYSTEM_LOCATION_ERROR,
                    f"Approved PJM power location {location_id} must have official_pjm_data_miner_verified pnode_source_status",
                )
            resolved[location_id] = {
                "operator_id": "PJM",
                "source_identity_policy": "official_pjm_data_miner_pnode_required",
                "pnode_id": pnode_id,
                "pnode_name": pnode_name,
                "pnode_type": pnode_type,
                "pnode_source_status": source_status,
            }
        else:
            resolved[location_id] = {
                "operator_id": str(record.get("iso_or_ba") or ""),
                "source_identity_policy": "operator_specific_pending",
            }
    return resolved


def approved_pjm_location_pnode_ids(registry_dir: Path) -> dict[int, str]:
    resolved = validate_power_location_source_identity_references(registry_dir)
    approved: dict[int, str] = {}
    for location_id, record in resolved.items():
        if record.get("operator_id") != "PJM":
            continue
        approved[int(record["pnode_id"])] = location_id
    return approved


def _require_positive_int(value: Any, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise WorkbenchException(POWER_SYSTEM_LOCATION_ERROR, f"{label} must be a positive integer") from exc
    if parsed < 1:
        raise WorkbenchException(POWER_SYSTEM_LOCATION_ERROR, f"{label} must be a positive integer")
    return parsed


def _require_nonempty(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise WorkbenchException(POWER_SYSTEM_LOCATION_ERROR, f"{label} is required")
    return text
