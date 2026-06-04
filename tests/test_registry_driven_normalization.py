from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.indices import normalize_gas_index, normalize_power_index
from pga_workbench.registry import validate_registries
from pga_workbench.registry_access import load_registry_catalog
from pga_workbench.spreads import decompose_power_spread


ROOT = Path(__file__).resolve().parents[1]


def _copy_registries(tmp_path: Path) -> Path:
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for path in (ROOT / "registries").glob("*.yaml"):
        shutil.copy(path, registry_dir / path.name)
    return registry_dir


def test_power_locations_are_loaded_from_registry(tmp_path):
    registry_dir = _copy_registries(tmp_path)
    power_locations = registry_dir / "power_locations.yaml"
    power_locations.write_text(
        power_locations.read_text(encoding="utf-8")
        + "\nXH:\n"
        + "  display_name: Example Hub\n"
        + "  commodity: power\n"
        + "  iso_or_ba: PJM\n"
        + "  location_type: hub\n"
        + "  default_market_run: RT\n"
        + "  default_price_component: FULL_LMP\n"
        + "  supported_market_runs: [DA, RT]\n"
        + "  supported_shapes: [PEAK, OFFPEAK, ATC]\n"
        + "  status: test_only\n",
        encoding="utf-8",
    )

    catalog = load_registry_catalog(registry_dir)
    index = normalize_power_index("XH DA peak", catalog)

    assert index.index_id == "PJM.XH.DA.FULL_LMP.PEAK"
    assert index.location_id == "XH"


def test_gas_locations_and_aliases_are_loaded_from_registry(tmp_path):
    registry_dir = _copy_registries(tmp_path)
    gas_locations = registry_dir / "gas_locations.yaml"
    gas_locations.write_text(
        gas_locations.read_text(encoding="utf-8")
        + "\nTEST_GAS:\n"
        + "  display_name: Test Gas Point\n"
        + "  aliases: [TGPX]\n"
        + "  commodity: gas\n"
        + "  pipe_group: Test\n"
        + "  region: Test\n"
        + "  location_type: index_point\n"
        + "  default_index_family: GDD\n"
        + "  status: test_only\n",
        encoding="utf-8",
    )

    catalog = load_registry_catalog(registry_dir)
    index = normalize_gas_index("TGPX", catalog)

    assert index.index_id == "GAS.TEST_GAS.GDD"
    assert index.is_defaulted is True


def test_spreads_are_loaded_from_registry(tmp_path):
    registry_dir = _copy_registries(tmp_path)
    quoted_spreads = registry_dir / "quoted_spreads.yaml"
    quoted_spreads.write_text(
        quoted_spreads.read_text(encoding="utf-8")
        + "\nXH/WH:\n"
        + "  commodity: power\n"
        + "  first: XH\n"
        + "  second: WH\n"
        + "  formula: first_minus_second\n"
        + "  basis_price_component: FULL_LMP\n"
        + "  approved_orientation: true\n",
        encoding="utf-8",
    )

    catalog = load_registry_catalog(registry_dir)
    spread = decompose_power_spread("XH/WH", 12, catalog)

    assert spread.first == "XH"
    assert spread.second == "WH"
    assert spread.first_leg_exposure == 12
    assert spread.second_leg_exposure == -12


def test_default_registries_have_full_schema_handlers():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")
    assert result.warnings == []


def test_temp_registry_duplicate_alias_fails_closed(tmp_path):
    registry_dir = _copy_registries(tmp_path)
    gas_locations = registry_dir / "gas_locations.yaml"
    gas_locations.write_text(
        gas_locations.read_text(encoding="utf-8")
        + "\nALIAS_COLLISION:\n"
        + "  display_name: Alias Collision\n"
        + "  aliases: [HH]\n"
        + "  commodity: gas\n"
        + "  pipe_group: Test\n"
        + "  region: Test\n"
        + "  location_type: index_point\n"
        + "  default_index_family: GDD\n"
        + "  status: test_only\n",
        encoding="utf-8",
    )

    with pytest.raises(WorkbenchException):
        load_registry_catalog(registry_dir)
