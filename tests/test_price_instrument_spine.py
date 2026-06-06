from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.exceptions import WorkbenchException, UNSUPPORTED_VOL_SURFACE
from pga_workbench.registry import validate_registries
from pga_workbench.registry_access import find_option_contract, load_registry_catalog
from pga_workbench.services.greeks import run_black76_greeks
from pga_workbench.services.normalization import normalize_positions
from pga_workbench.services.pnl import run_pnl_attribution


ROOT = Path(__file__).resolve().parents[1]


def test_option_contract_registry_validates_and_resolves_ice_options():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")

    assert "option_contracts.yaml" in result.validated_files
    assert result.warnings == []

    catalog = load_registry_catalog()
    assert catalog.option_contracts["ICE_PMI_OPTION_PJM_WH_RT_PEAK_1MW"]["contract_symbol"] == "PMI"
    assert catalog.option_contracts["ICE_P1X_OPTION_PJM_WH_RT_PEAK_CAL_YEAR_1X"]["contract_symbol"] == "P1X"
    assert catalog.option_contracts["ICE_PHE_OPTION_HENRY_PENULTIMATE_FIXED_PRICE"]["contract_symbol"] == "PHE"

    pmi = find_option_contract("PMI")
    p1x = find_option_contract("P1X")
    phe = find_option_contract("PHE")

    assert pmi["option_style"] == "American"
    assert pmi["underlying_contract_id"] == "ICE_PMI_PJM_WH_RT_PEAK_1MW"
    assert p1x["contract_period"] == "annual_strip"
    assert p1x["exercise_method"] == "Automatic Only"
    assert phe["underlying_index_id"] == "GAS.HH.NYMEX_PENULTIMATE"
    assert phe["strike_price_listing"]["standard_increment"] == "USD 0.25 per MMBtu"


def test_position_normalization_emits_lot_exposures_and_reporting_metadata():
    positions = normalize_positions(
        [
            {
                "as_of": "2026-06-04T12:00:00Z",
                "position_id": "P1",
                "raw_product": "WH",
                "raw_period": "N26",
                "raw_quantity": "10",
                "quantity_unit": "MW",
                "reference_hours": "16",
                "raw_mark": "55",
                "book": "PJM",
                "strategy": "heat-rate",
                "portfolio": "east",
                "sleeve": "winter",
                "tags": "hedge, prompt",
                "metadata": "{\"custom_group\": \"western_hub\"}",
            }
        ]
    )

    position = positions[0]
    assert position.identity["book"] == "PJM"
    assert position.identity["portfolio"] == "east"
    assert position.identity["tags"] == ["hedge", "prompt"]
    assert position.identity["metadata"] == {"custom_group": "western_hub"}
    assert position.position_lot["instrument_id"] == "PJM.WH.RT.FULL_LMP.ATC.N26"
    assert position.position_lot["sleeve"] == "winter"
    assert position.exposures == [
        {
            "as_of": "2026-06-04T12:00:00Z",
            "position_id": "P1",
            "index_id": "PJM.WH.RT.FULL_LMP.ATC.N26",
            "period_id": "N26",
            "signed_quantity": 10.0,
            "quantity_unit": "MW",
            "exposure_type": "flat_price",
            "component": None,
            "component_weight": 1.0,
            "derived_MWh": 160.0,
            "derived_MMBtu": None,
            "market_value": 8800.0,
            "book": "PJM",
            "strategy": "heat-rate",
            "portfolio": "east",
            "sleeve": "winter",
            "structure_id": None,
            "tags": ["hedge", "prompt"],
            "metadata": {"custom_group": "western_hub"},
        }
    ]


def test_pnl_attribution_rolls_up_position_metadata_groups_and_tags():
    prior = normalize_positions(
        [
            {
                "as_of": "2026-06-03T12:00:00Z",
                "position_id": "P1",
                "raw_product": "WH",
                "raw_period": "N26",
                "raw_quantity": "10",
                "quantity_unit": "MW",
                "reference_hours": "10",
                "raw_mark": "50",
                "book": "PJM",
                "strategy": "hedge",
                "portfolio": "east",
                "sleeve": "summer",
                "tags": "basis,wh",
            }
        ]
    )
    current = normalize_positions(
        [
            {
                "as_of": "2026-06-04T12:00:00Z",
                "position_id": "P1",
                "raw_product": "WH",
                "raw_period": "N26",
                "raw_quantity": "12",
                "quantity_unit": "MW",
                "reference_hours": "10",
                "raw_mark": "55",
                "book": "PJM",
                "strategy": "hedge",
                "portfolio": "east",
                "sleeve": "summer",
                "tags": "basis,wh",
            }
        ]
    )

    report = run_pnl_attribution(prior, current)
    group_map = {(item["dimension"], item["value"]): item for item in report.group_breakdowns}

    assert report.drivers[0]["identity"]["book"] == "PJM"
    assert group_map[("book", "PJM")]["total_effect"] == 1600
    assert group_map[("strategy", "hedge")]["price_move_effect"] == 500
    assert group_map[("portfolio", "east")]["position_change_effect"] == 1100
    assert group_map[("sleeve", "summer")]["total_effect"] == 1600
    assert group_map[("tag", "basis")]["total_effect"] == 1600
    assert group_map[("tag", "wh")]["total_effect"] == 1600


def test_registered_option_greeks_include_contract_metadata_and_model_scope():
    report = run_black76_greeks(
        [
            {
                "as_of": "2026-06-04T12:00:00Z",
                "option_contract_id": "ICE_PMI_OPTION_PJM_WH_RT_PEAK_1MW",
                "option_id": "PMI-C-50-N26",
                "delivery_period_id": "N26",
                "option_type": "call",
                "position": "2",
                "forward": "50",
                "strike": "50",
                "volatility": "0.4",
                "time_to_expiry_years": "0.5",
            },
            {
                "as_of": "2026-06-04T12:00:00Z",
                "option_symbol": "PHE",
                "option_id": "PHE-P-3.50-N26",
                "delivery_period_id": "N26",
                "option_type": "put",
                "position": "1",
                "forward": "3.5",
                "strike": "3.5",
                "volatility": "0.35",
                "time_to_expiry_years": "0.25",
            },
        ]
    )

    pmi = report.greeks[0]
    phe = report.greeks[1]
    assert pmi["option_contract_id"] == "ICE_PMI_OPTION_PJM_WH_RT_PEAK_1MW"
    assert pmi["contract_symbol"] == "PMI"
    assert pmi["option_style"] == "American"
    assert pmi["analytics_scope"] == "screening_only"
    assert pmi["vol_input_scope"] == "single_point_black76_input"
    assert pmi["model_scope"] == "screening_greeks_only_american_exercise_not_modeled"
    assert pmi["position_delta"] > 1.0
    assert phe["option_contract_id"] == "ICE_PHE_OPTION_HENRY_PENULTIMATE_FIXED_PRICE"
    assert phe["underlying_index_id"] == "GAS.HH.NYMEX_PENULTIMATE"
    assert phe["premium_quote_unit"] == "USD_per_MMBtu"
    assert report.lineage["analytics_scope"] == "screening_only"
    assert report.lineage["exceptions"][0]["code"] == "OPTION_STYLE_APPROXIMATION"


def test_registered_option_greeks_keep_vol_scope_fail_closed():
    with pytest.raises(WorkbenchException) as exc:
        run_black76_greeks(
            [
                {
                    "as_of": "2026-06-04T12:00:00Z",
                    "location_id": "AD",
                    "underlying_index_id": "PJM.AD.RT.FULL_LMP.PEAK.N26",
                    "delivery_period_id": "N26",
                    "option_type": "call",
                    "forward": "50",
                    "strike": "50",
                    "volatility": "0.4",
                    "time_to_expiry_years": "0.5",
                }
            ]
        )

    assert exc.value.code == UNSUPPORTED_VOL_SURFACE
