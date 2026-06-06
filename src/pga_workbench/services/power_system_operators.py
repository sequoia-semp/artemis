from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique

POWER_SYSTEM_OPERATOR_ERROR = "POWER_SYSTEM_OPERATOR_ERROR"


def load_power_system_operators(registry_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_yaml_unique(Path(registry_dir) / "power_system_operators.yaml")
    if not isinstance(data, dict):
        raise WorkbenchException(POWER_SYSTEM_OPERATOR_ERROR, "power_system_operators.yaml must be a mapping")
    return {str(key): dict(value) for key, value in data.items() if isinstance(value, dict)}


def _require_operator(operator_ids: set[str], value: Any, label: str) -> str:
    operator_id = str(value)
    if operator_id not in operator_ids:
        raise WorkbenchException(POWER_SYSTEM_OPERATOR_ERROR, f"{label} references unknown power system operator: {operator_id}")
    return operator_id


def _load_optional_mapping(registry_dir: Path, name: str) -> dict[str, Any]:
    path = Path(registry_dir) / name
    if not path.exists():
        return {}
    data = load_yaml_unique(path)
    return data if isinstance(data, dict) else {}


def validate_power_system_operator_references(registry_dir: Path) -> dict[str, list[str]]:
    registry_dir = Path(registry_dir)
    operators = load_power_system_operators(registry_dir)
    operator_ids = set(operators)
    references: dict[str, list[str]] = {operator_id: [] for operator_id in sorted(operator_ids)}

    source_catalog = _load_optional_mapping(registry_dir, "power_system_source_catalog.yaml")
    for publication_id, record in source_catalog.items():
        if not isinstance(record, dict):
            continue
        operator_id = _require_operator(operator_ids, record.get("market_operator"), f"power_system_source_catalog:{publication_id}")
        references[operator_id].append(f"power_system_source_catalog:{publication_id}")

    power_locations = _load_optional_mapping(registry_dir, "power_locations.yaml")
    for location_id, record in power_locations.items():
        if not isinstance(record, dict) or record.get("commodity") != "power":
            continue
        operator_id = _require_operator(operator_ids, record.get("iso_or_ba"), f"power_locations:{location_id}")
        references[operator_id].append(f"power_locations:{location_id}")

    for registry_name in [
        "pjm_fundamental_feeds.yaml",
        "pjm_load_areas.yaml",
        "power_system_price_feeds.yaml",
        "power_generation_mix_feeds.yaml",
        "power_system_operational_event_feeds.yaml",
    ]:
        data = _load_optional_mapping(registry_dir, registry_name)
        for item_id, record in data.items():
            if not isinstance(record, dict):
                continue
            operator_id = _require_operator(operator_ids, record.get("operator_id") or record.get("market"), f"{registry_name}:{item_id}")
            references[operator_id].append(f"{registry_name}:{item_id}")

    calendars = _load_optional_mapping(registry_dir, "power_market_calendars.yaml")
    for calendar_id, record in calendars.items():
        if not isinstance(record, dict):
            continue
        market = str(record.get("market"))
        if market == "NORTH_AMERICA_POWER":
            continue
        operator_id = _require_operator(operator_ids, market, f"power_market_calendars:{calendar_id}")
        references[operator_id].append(f"power_market_calendars:{calendar_id}")

    return references
