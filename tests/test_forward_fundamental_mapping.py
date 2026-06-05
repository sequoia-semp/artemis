from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.indices import normalize_exchange_contract_index
from pga_workbench.registry import REGISTRY_VALIDATION_ERROR, validate_registries
from pga_workbench.registry_access import find_forward_fundamental_mapping, load_registry_catalog
from pga_workbench.services.normalization import normalize_marks


ROOT = Path(__file__).resolve().parents[1]

MONTHLY_PJM_POWER_MAPPINGS = {
    "PJC": ("WH", "DA", "PEAK", 51288, "WESTERN HUB"),
    "PJD": ("WH", "DA", "OFFPEAK", 51288, "WESTERN HUB"),
    "PMI": ("WH", "RT", "PEAK", 51288, "WESTERN HUB"),
    "OPJ": ("WH", "RT", "OFFPEAK", 51288, "WESTERN HUB"),
    "ADB": ("AD", "DA", "PEAK", 34497127, "AEP-DAYTON HUB"),
    "ADD": ("AD", "DA", "OFFPEAK", 34497127, "AEP-DAYTON HUB"),
    "MSO": ("AD", "RT", "PEAK", 34497127, "AEP-DAYTON HUB"),
    "AOD": ("AD", "RT", "OFFPEAK", 34497127, "AEP-DAYTON HUB"),
    "NIB": ("NI", "DA", "PEAK", 33092315, "N ILLINOIS HUB"),
    "NID": ("NI", "DA", "OFFPEAK", 33092315, "N ILLINOIS HUB"),
    "PNL": ("NI", "RT", "PEAK", 33092315, "N ILLINOIS HUB"),
    "NIO": ("NI", "RT", "OFFPEAK", 33092315, "N ILLINOIS HUB"),
}

ICE_GAS_INDEX_MAPPINGS = {
    "H": ("GAS.HH.LD1", "HH", "LD1"),
    "BM1": ("GAS.TETCO_M2.IFERC", "TETCO_M2", "IFERC"),
    "BM2": ("GAS.TETCO_M2.BASIS_TO_LD1", "TETCO_M2", "BASIS_TO_LD1"),
    "BM3": ("GAS.TETCO_M2.GDD", "TETCO_M2", "GDD"),
    "MB4": ("GAS.TETCO_M2.GDD_INDEX_TO_IFERC", "TETCO_M2", "GDD_INDEX_TO_IFERC"),
    "TMT": ("GAS.TETCO_M3.BASIS_TO_LD1", "TETCO_M3", "BASIS_TO_LD1"),
    "MTI": ("GAS.TETCO_M3.GDD_INDEX_TO_IFERC", "TETCO_M3", "GDD_INDEX_TO_IFERC"),
    "TZ6": ("GAS.TRANSCO_Z6_NY.IFERC", "TRANSCO_Z6_NY", "IFERC"),
    "ZSS": ("GAS.TRANSCO_Z6_NY.GDD", "TRANSCO_Z6_NY", "GDD"),
    "TZS": ("GAS.TRANSCO_Z6_NY.BASIS_TO_LD1", "TRANSCO_Z6_NY", "BASIS_TO_LD1"),
    "TPH": ("GAS.TRANSCO_Z6_NNY.IFERC", "TRANSCO_Z6_NNY", "IFERC"),
    "TPB": ("GAS.TRANSCO_Z6_NNY.BASIS_TO_LD1", "TRANSCO_Z6_NNY", "BASIS_TO_LD1"),
    "TPS": ("GAS.TRANSCO_Z6_NNY.GDD", "TRANSCO_Z6_NNY", "GDD"),
    "TPI": ("GAS.TRANSCO_Z6_NNY.GDD_INDEX_TO_IFERC", "TRANSCO_Z6_NNY", "GDD_INDEX_TO_IFERC"),
    "TZ5": ("GAS.TRANSCO_Z5.IFERC", "TRANSCO_Z5", "IFERC"),
    "DKR": ("GAS.TRANSCO_Z5.BASIS_TO_LD1", "TRANSCO_Z5", "BASIS_TO_LD1"),
    "DKS": ("GAS.TRANSCO_Z5.GDD", "TRANSCO_Z5", "GDD"),
    "DKT": ("GAS.TRANSCO_Z5.GDD_INDEX_TO_IFERC", "TRANSCO_Z5", "GDD_INDEX_TO_IFERC"),
    "T5Z": ("GAS.TRANSCO_Z5_SOUTH.IFERC", "TRANSCO_Z5_SOUTH", "IFERC"),
    "T5B": ("GAS.TRANSCO_Z5_SOUTH.BASIS_TO_LD1", "TRANSCO_Z5_SOUTH", "BASIS_TO_LD1"),
    "T5C": ("GAS.TRANSCO_Z5_SOUTH.GDD", "TRANSCO_Z5_SOUTH", "GDD"),
    "T5I": ("GAS.TRANSCO_Z5_SOUTH.GDD_INDEX_TO_IFERC", "TRANSCO_Z5_SOUTH", "GDD_INDEX_TO_IFERC"),
    "DOM": ("GAS.EASTERN_GAS_SOUTH.BASIS_TO_LD1", "EASTERN_GAS_SOUTH", "BASIS_TO_LD1"),
    "DIS": ("GAS.EASTERN_GAS_SOUTH.GDD_INDEX_TO_IFERC", "EASTERN_GAS_SOUTH", "GDD_INDEX_TO_IFERC"),
}


def _copy_registries(tmp_path: Path) -> Path:
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for path in (ROOT / "registries").glob("*.yaml"):
        shutil.copy(path, registry_dir / path.name)
    return registry_dir


def test_ice_pmi_pdp_contract_and_mapping_registries_validate():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")

    assert "exchange_contracts.yaml" in result.validated_files
    assert "forward_fundamental_mappings.yaml" in result.validated_files
    assert result.warnings == []

    catalog = load_registry_catalog()
    assert catalog.exchange_contracts["ICE_PMI_PJM_WH_RT_PEAK_1MW"]["contract_symbol"] == "PMI"
    assert catalog.exchange_contracts["ICE_PDP_PJM_WH_RT_PEAK_DAILY"]["contract_symbol"] == "PDP"
    assert catalog.exchange_contracts["ICE_TZS_TRANSCO_Z6_NY_BASIS_FUTURE"]["contract_symbol"] == "TZS"
    assert catalog.exchange_contracts["ICE_MTI_TETCO_M3_INDEX_FUTURE"]["index_family"] == "GDD_INDEX_TO_IFERC"
    assert catalog.exchange_contracts["ICE_BM2_TETCO_M2_BASIS_RECEIPTS"]["contract_symbol"] == "BM2"
    assert catalog.exchange_contracts["ICE_T5I_TRANSCO_Z5_SOUTH_INDEX_FUTURE"]["index_family"] == "GDD_INDEX_TO_IFERC"


def test_ice_contract_symbols_resolve_to_pjm_western_hub_rt_peak_lmp():
    pmi = normalize_exchange_contract_index("PMI")
    pdp = normalize_exchange_contract_index("ICE PDP")

    for index in [pmi, pdp]:
        assert index.index_id == "PJM.WH.RT.FULL_LMP.PEAK"
        assert index.location_id == "WH"
        assert index.market_run == "RT"
        assert index.price_component == "FULL_LMP"
        assert index.shape == "PEAK"
        assert index.is_defaulted is False

    assert pmi.source_contract_id == "ICE_PMI_PJM_WH_RT_PEAK_1MW"
    assert pdp.source_contract_id == "ICE_PDP_PJM_WH_RT_PEAK_DAILY"


@pytest.mark.parametrize("symbol,expected", sorted(MONTHLY_PJM_POWER_MAPPINGS.items()))
def test_monthly_pjm_power_contract_symbols_resolve_to_canonical_indices(symbol, expected):
    location_id, market_run, shape, _pnode_id, _pnode_name = expected

    index = normalize_exchange_contract_index(symbol)

    assert index.index_id == f"PJM.{location_id}.{market_run}.FULL_LMP.{shape}"
    assert index.location_id == location_id
    assert index.market_run == market_run
    assert index.price_component == "FULL_LMP"
    assert index.shape == shape
    assert index.quote_unit == "USD_per_MWh"
    assert index.is_defaulted is False


def test_forward_mapping_preserves_pjm_pnode_and_peak_aggregation_rule():
    mapping = find_forward_fundamental_mapping("PJM WH RT PMI")

    assert mapping["target"]["pnode_id"] == 51288
    assert mapping["target"]["pnode_name"] == "WESTERN HUB"
    assert mapping["target"]["pjm_lmp_feed"] == "rt_hrl_lmps"
    assert mapping["aggregation_rule"]["hours_ending_ept"] == list(range(8, 24))
    assert mapping["verification_status"] == "official_exchange_verified_user_pnode_approved"


@pytest.mark.parametrize("symbol,expected", sorted(MONTHLY_PJM_POWER_MAPPINGS.items()))
def test_monthly_pjm_power_mappings_preserve_pnode_feeds_and_shape_rules(symbol, expected):
    location_id, market_run, shape, pnode_id, pnode_name = expected
    mapping = find_forward_fundamental_mapping(symbol)

    assert mapping["target"]["index_id"] == f"PJM.{location_id}.{market_run}.FULL_LMP.{shape}"
    assert mapping["target"]["pnode_id"] == pnode_id
    assert mapping["target"]["pnode_name"] == pnode_name
    assert mapping["target"]["pjm_lmp_feed"] == ("da_hrl_lmps" if market_run == "DA" else "rt_hrl_lmps")
    if shape == "PEAK":
        assert mapping["aggregation_rule"]["hours_ending_ept"] == list(range(8, 24))
    else:
        assert mapping["aggregation_rule"]["rule_id"] == "PJM_OFFPEAK_5X8_2X24_EPT"
        assert mapping["aggregation_rule"]["hours_ending_ept"] == [1, 2, 3, 4, 5, 6, 7, 24]


def test_raw_ice_contract_mark_normalizes_to_target_index_with_lineage():
    points = normalize_marks(
        [
            {
                "as_of": "2026-06-05T12:00:00Z",
                "raw_product": "PMI",
                "raw_period": "N26",
                "price": "72.50",
                "source": "ice_fixture",
            }
        ]
    )

    assert points[0].index_id == "PJM.WH.RT.FULL_LMP.PEAK.N26"
    assert points[0].quote_unit == "USD_per_MWh"
    assert points[0].lineage["source_contract_id"] == "ICE_PMI_PJM_WH_RT_PEAK_1MW"
    assert points[0].lineage["mapping_id"] == "ICE_PMI_TO_PJM_WH_RT_LMP_51288"


def test_offpeak_symbol_opj_normalizes_to_western_hub_rt_offpeak():
    points = normalize_marks(
        [
            {
                "as_of": "2026-06-05T12:00:00Z",
                "raw_product": "OPJ",
                "raw_period": "N26",
                "price": "42.25",
                "source": "ice_fixture",
            }
        ]
    )

    assert points[0].index_id == "PJM.WH.RT.FULL_LMP.OFFPEAK.N26"
    assert points[0].lineage["source_contract_id"] == "ICE_OPJ_PJM_WH_RT_OFFPEAK_1MW"
    assert points[0].lineage["mapping_id"] == "ICE_OPJ_TO_PJM_WH_RT_LMP_51288"


@pytest.mark.parametrize("symbol,expected", sorted(ICE_GAS_INDEX_MAPPINGS.items()))
def test_ice_gas_contract_symbols_resolve_to_canonical_gas_indices(symbol, expected):
    index_id, location_id, index_family = expected

    index = normalize_exchange_contract_index(symbol)

    assert index.index_id == index_id
    assert index.commodity == "gas"
    assert index.location_id == location_id
    assert index.index_family == index_family
    assert index.market_run is None
    assert index.price_component is None
    assert index.quote_unit == "USD_per_MMBtu"
    assert index.is_defaulted is False


def test_gas_basis_mapping_preserves_official_a_minus_b_formula_legs():
    mapping = find_forward_fundamental_mapping("Transco Z6 NY Basis")

    assert mapping["mapping_type"] == "gas_basis_contract_to_formula"
    assert mapping["target"]["index_id"] == "GAS.TRANSCO_Z6_NY.BASIS_TO_LD1"
    assert mapping["target"]["formula"]["formula_type"] == "REFERENCE_PRICE_A_MINUS_B"
    assert mapping["target"]["formula"]["legs"] == [
        {
            "leg": "A",
            "operation": "add",
            "index_id": "GAS.TRANSCO_Z6_NY.IFERC",
            "index_family": "IFERC",
        },
        {
            "leg": "B",
            "operation": "subtract",
            "index_id": "GAS.HH.LD1",
            "index_family": "LD1",
        },
    ]
    assert mapping["verification_status"] == "official_exchange_verified"


def test_new_gas_basis_mapping_preserves_location_specific_formula_legs():
    mapping = find_forward_fundamental_mapping("DKR")

    assert mapping["mapping_type"] == "gas_basis_contract_to_formula"
    assert mapping["target"]["index_id"] == "GAS.TRANSCO_Z5.BASIS_TO_LD1"
    assert mapping["target"]["formula"]["legs"] == [
        {
            "leg": "A",
            "operation": "add",
            "index_id": "GAS.TRANSCO_Z5.IFERC",
            "index_family": "IFERC",
        },
        {
            "leg": "B",
            "operation": "subtract",
            "index_id": "GAS.HH.LD1",
            "index_family": "LD1",
        },
    ]


def test_gas_index_mapping_preserves_average_gdd_minus_iferc_formula_legs():
    mapping = find_forward_fundamental_mapping("MTI")

    assert mapping["mapping_type"] == "gas_index_contract_to_formula"
    assert mapping["target"]["index_id"] == "GAS.TETCO_M3.GDD_INDEX_TO_IFERC"
    assert mapping["target"]["formula"]["formula_type"] == "AVERAGE_REFERENCE_PRICE_A_MINUS_B"
    assert mapping["target"]["formula"]["legs"][0]["index_id"] == "GAS.TETCO_M3.GDD"
    assert mapping["target"]["formula"]["legs"][0]["aggregation"] == "average_over_contract_period"
    assert mapping["target"]["formula"]["legs"][1]["index_id"] == "GAS.TETCO_M3.IFERC"


def test_new_gas_index_mapping_preserves_average_gdd_minus_iferc_formula_legs():
    mapping = find_forward_fundamental_mapping("T5I")

    assert mapping["mapping_type"] == "gas_index_contract_to_formula"
    assert mapping["target"]["index_id"] == "GAS.TRANSCO_Z5_SOUTH.GDD_INDEX_TO_IFERC"
    assert mapping["target"]["formula"]["formula_type"] == "AVERAGE_REFERENCE_PRICE_A_MINUS_B"
    assert mapping["target"]["formula"]["legs"][0]["index_id"] == "GAS.TRANSCO_Z5_SOUTH.GDD"
    assert mapping["target"]["formula"]["legs"][0]["aggregation"] == "average_over_contract_period"
    assert mapping["target"]["formula"]["legs"][1]["index_id"] == "GAS.TRANSCO_Z5_SOUTH.IFERC"


def test_raw_ice_gas_contract_mark_normalizes_to_target_index_with_lineage():
    points = normalize_marks(
        [
            {
                "as_of": "2026-06-05T12:00:00Z",
                "raw_product": "TMT",
                "raw_period": "N26",
                "price": "-1.125",
                "source": "ice_fixture",
            }
        ]
    )

    assert points[0].index_id == "GAS.TETCO_M3.BASIS_TO_LD1.N26"
    assert points[0].quote_unit == "USD_per_MMBtu"
    assert points[0].lineage["source_contract_id"] == "ICE_TMT_TETCO_M3_BASIS_FUTURE"
    assert points[0].lineage["mapping_id"] == "ICE_TMT_TO_GAS_TETCO_M3_BASIS_TO_LD1"


def test_exchange_contract_source_documents_are_required(tmp_path):
    registry_dir = _copy_registries(tmp_path)
    contracts = registry_dir / "exchange_contracts.yaml"
    contracts.write_text(
        contracts.read_text(encoding="utf-8").replace(
            "  source_documents:\n"
            "    - authority: ICE product specification\n"
            "      url: https://www.ice.com/products/6590369/PJM-Western-Hub-Real-Time-Peak-1-MW-Fixed-Price-Future\n"
            "      notes: Official ICE product page for PMI contract metadata and Reference Price A.\n"
            "    - authority: ICE product specification PDF\n"
            "      url: https://www.ice.com/api/productguide/spec/6590369/pdf\n"
            "      notes: Official ICE PDF spec retrieved during CR-0010 implementation.\n",
            "  source_documents: []\n",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(WorkbenchException) as exc:
        validate_registries(registry_dir, ROOT / "schemas")

    assert exc.value.code == REGISTRY_VALIDATION_ERROR
