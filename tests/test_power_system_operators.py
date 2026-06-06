from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.registry import load_yaml_unique, validate_registries
from pga_workbench.services.power_system_operators import (
    POWER_SYSTEM_OPERATOR_ERROR,
    load_power_system_operators,
    validate_power_system_operator_references,
)


ROOT = Path(__file__).resolve().parents[1]


def test_power_system_operator_registry_validates_without_warnings():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")
    operators = load_power_system_operators(ROOT / "registries")

    assert "power_system_operators.yaml" in result.validated_files
    assert result.warnings == []
    assert operators["PJM"]["operator_kind"] == "rto_iso"
    assert operators["PJM"]["settlement_timezone"] == "America/New_York"
    assert "pjm_data_miner_api" in operators["PJM"]["data_access_surfaces"]


def test_power_system_operator_references_cover_pjm_registries():
    references = validate_power_system_operator_references(ROOT / "registries")

    assert "power_system_source_catalog:PJM_DATAMINER_HOURLY_LMP_CORE" in references["PJM"]
    assert "power_locations:WH" in references["PJM"]
    assert "power_system_price_feeds.yaml:PJM_RT_HOURLY_LMP" in references["PJM"]
    assert "power_generation_mix_feeds.yaml:PJM_GEN_BY_FUEL" in references["PJM"]
    assert "power_system_operational_event_feeds.yaml:PJM_RT_TRANSN_CONSTRAINTS" in references["PJM"]
    assert "power_market_calendars:PJM_EPT_POWER_DAY" in references["PJM"]


def test_unknown_power_system_operator_reference_fails_closed(tmp_path):
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in [
        "power_system_operators.yaml",
        "power_system_source_catalog.yaml",
        "power_locations.yaml",
        "pjm_fundamental_feeds.yaml",
        "pjm_load_areas.yaml",
        "power_system_price_feeds.yaml",
        "power_generation_mix_feeds.yaml",
        "power_system_operational_event_feeds.yaml",
        "power_market_calendars.yaml",
    ]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")

    locations = load_yaml_unique(registry_dir / "power_locations.yaml")
    locations["WH"]["iso_or_ba"] = "UNKNOWN_ISO"
    (registry_dir / "power_locations.yaml").write_text(yaml.safe_dump(locations, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_operator_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_OPERATOR_ERROR
    assert "UNKNOWN_ISO" in exc.value.message
