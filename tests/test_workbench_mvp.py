from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from pga_workbench.adapters.pjm import load_pjm_fundamental_fixture
from pga_workbench.agent.memory import MUTATING_AGENT_ACTION_BLOCKED, assert_read_only_action, draft_change_request
from pga_workbench.cache.hot_state import HotState
from pga_workbench.cli import main
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.models import AgentMemoryEntry, RunManifest
from pga_workbench.registry import REGISTRY_VALIDATION_ERROR, SHARED_READONLY_PUBLISH_BLOCKED, SYNTHETIC_PROMOTION_BLOCKED, load_yaml_unique, validate_registries
from pga_workbench.serialization import read_json, write_json
from pga_workbench.services.greeks import black76_greeks, run_black76_greeks
from pga_workbench.services.normalization import normalize_marks, normalize_positions
from pga_workbench.services.pnl import run_pnl_attribution
from pga_workbench.services.risk import run_historical_var
from pga_workbench.state.packs import build_candidate_state_pack, publish_candidate_state_pack


ROOT = Path(__file__).resolve().parents[1]


def test_validate_registries_accepts_seed_packet():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")
    assert "quoted_spreads.yaml" in result.validated_files
    assert result.checked_records >= 20


def test_validate_registries_rejects_forbidden_spread_as_approved(tmp_path):
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for path in (ROOT / "registries").glob("*.yaml"):
        (registry_dir / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    quoted = registry_dir / "quoted_spreads.yaml"
    quoted.write_text(
        quoted.read_text(encoding="utf-8")
        + "\nAD/WH:\n  commodity: power\n  first: AD\n  second: WH\n  formula: first_minus_second\n  approved_orientation: true\n",
        encoding="utf-8",
    )
    with pytest.raises(WorkbenchException) as exc:
        validate_registries(registry_dir, ROOT / "schemas")
    assert exc.value.code == REGISTRY_VALIDATION_ERROR


def test_validate_registries_rejects_gas_contract_convention_change(tmp_path):
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for path in (ROOT / "registries").glob("*.yaml"):
        (registry_dir / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    quantity = registry_dir / "quantity_conventions.yaml"
    quantity.write_text(quantity.read_text(encoding="utf-8").replace("d_per_contract: 0.25", "d_per_contract: 1.0"), encoding="utf-8")
    with pytest.raises(WorkbenchException) as exc:
        validate_registries(registry_dir, ROOT / "schemas")
    assert exc.value.code == REGISTRY_VALIDATION_ERROR


def test_duplicate_yaml_keys_fail_closed(tmp_path):
    path = tmp_path / "dupe.yaml"
    path.write_text("A:\n  value: 1\nA:\n  value: 2\n", encoding="utf-8")
    with pytest.raises(WorkbenchException) as exc:
        load_yaml_unique(path)
    assert exc.value.code == REGISTRY_VALIDATION_ERROR


def test_normalize_marks_and_positions_preserve_lineage_and_values():
    marks = normalize_marks(
        [
            {"as_of": "2026-06-04T12:00:00Z", "raw_product": "WH RT ATC", "raw_period": "N26", "price": "55", "source": "marks_csv"},
            {"as_of": "2026-06-04T12:00:00Z", "raw_product": "HH", "raw_period": "N26", "price": "3", "source": "marks_csv"},
        ]
    )
    assert marks[0].index_id == "PJM.WH.RT.FULL_LMP.ATC.N26"
    assert marks[0].lineage["raw_product"] == "WH RT ATC"

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
            },
            {
                "as_of": "2026-06-04T12:00:00Z",
                "position_id": "G1",
                "raw_product": "HH",
                "raw_period": "N26",
                "raw_quantity": "1",
                "quantity_unit": "contracts",
                "delivery_days": "30",
            },
        ],
        marks,
    )
    assert positions[0].derived["derived_MWh"] == 160
    assert positions[0].derived["market_value"] == 8800
    assert positions[1].derived["derived_MMBtu"] == 75000
    assert positions[1].derived["market_value"] == 225000


def test_normalize_position_rejects_unknown_product():
    with pytest.raises(WorkbenchException):
        normalize_positions(
            [
                {
                    "as_of": "2026-06-04T12:00:00Z",
                    "position_id": "X1",
                    "raw_product": "UNKNOWN",
                    "raw_period": "N26",
                    "raw_quantity": "1",
                    "quantity_unit": "MW",
                    "reference_hours": "16",
                }
            ]
        )


def test_pnl_attribution_splits_price_and_position_changes():
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
            }
        ]
    )
    report = run_pnl_attribution(prior, current)
    assert report.price_move_effect == 500
    assert report.position_change_effect == 1100
    assert report.bridge_sums is True


def test_historical_var_reports_95_and_99_losses():
    position = normalize_positions(
        [
            {
                "as_of": "2026-06-04T12:00:00Z",
                "position_id": "P1",
                "raw_product": "WH",
                "raw_period": "N26",
                "raw_quantity": "10",
                "quantity_unit": "MW",
                "reference_hours": "10",
                "raw_mark": "50",
            }
        ]
    )
    returns = [
        {"date": "d1", "risk_factor": "PJM.WH.RT.FULL_LMP.ATC.N26", "return": -0.01},
        {"date": "d2", "risk_factor": "PJM.WH.RT.FULL_LMP.ATC.N26", "return": 0.02},
        {"date": "d3", "risk_factor": "PJM.WH.RT.FULL_LMP.ATC.N26", "return": -0.05},
    ]
    report = run_historical_var(position, returns, "2026-06-04T12:00:00Z")
    assert report.var_by_confidence["95"] == 250
    assert report.var_by_confidence["99"] == 250
    assert report.horizon_days == 1


def test_black76_greeks_wh_hh_scope():
    greeks = black76_greeks("call", forward=50, strike=50, volatility=0.4, time_to_expiry_years=0.5)
    assert greeks["delta"] == pytest.approx(0.5562, rel=1e-3)

    report = run_black76_greeks(
        [
            {
                "as_of": "2026-06-04T12:00:00Z",
                "option_id": "O1",
                "location_id": "WH",
                "underlying_index_id": "PJM.WH.RT.FULL_LMP.ATC.N26",
                "delivery_period_id": "N26",
                "option_type": "call",
                "position": "2",
                "forward": "50",
                "strike": "50",
                "volatility": "0.4",
                "time_to_expiry_years": "0.5",
            }
        ]
    )
    assert report.model_convention == "Black76"
    assert report.greeks[0]["position_delta"] == pytest.approx(greeks["delta"] * 2)


def test_state_pack_candidate_publish_and_hot_state(tmp_path):
    manifest = RunManifest(run_id="state-1", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "state-1", "2026-06-04T12:00:00Z", {"prices": [{"value": 1}]}, manifest)
    assert (tmp_path / "candidates" / "state-1" / "state_pack.json").exists()
    accepted = publish_candidate_state_pack(tmp_path, "state-1")
    assert accepted.exists()
    assert not (tmp_path / "candidates" / "state-1").exists()
    assert HotState(tmp_path).artifacts()["prices"][0]["value"] == 1


def test_state_pack_validation_rejects_non_utc_and_manifest_mismatch(tmp_path):
    manifest = RunManifest(run_id="bad-time", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    with pytest.raises(WorkbenchException) as exc:
        build_candidate_state_pack(tmp_path, "bad-time", "2026-06-04T12:00:00+00:00", {}, manifest)
    assert exc.value.code == "STATE_PACK_INVALID"

    mismatch = RunManifest(run_id="other-run", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    with pytest.raises(WorkbenchException) as exc:
        build_candidate_state_pack(tmp_path, "bad-manifest", "2026-06-04T12:00:00Z", {}, mismatch)
    assert exc.value.code == "STATE_PACK_INVALID"


def test_state_pack_validation_rejects_invalid_delivery_windows(tmp_path):
    manifest = RunManifest(run_id="bad-window", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    artifacts = {
        "observations": [
            {
                "delivery_start": "2026-06-04T14:00:00Z",
                "delivery_end": "2026-06-04T13:00:00Z",
                "value": 100,
            }
        ]
    }
    with pytest.raises(WorkbenchException) as exc:
        build_candidate_state_pack(tmp_path, "bad-window", "2026-06-04T12:00:00Z", artifacts, manifest)
    assert exc.value.code == "STATE_PACK_INVALID"


def test_state_pack_validation_rejects_candidate_artifact_products(tmp_path):
    manifest = RunManifest(run_id="bad-product", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")

    with pytest.raises(WorkbenchException) as exc:
        build_candidate_state_pack(
            tmp_path,
            "bad-product",
            "2026-06-04T12:00:00Z",
            {"power_system_operational_event_feeds": {}},
            manifest,
        )

    assert exc.value.code == "STATE_PACK_INVALID"
    assert "not approved for state-pack publish" in exc.value.message


def test_state_pack_blocks_synthetic_and_shared_readonly_publish(tmp_path):
    manifest = RunManifest(run_id="state-1", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "state-1", "2026-06-04T12:00:00Z", {}, manifest, synthetic=True)
    with pytest.raises(WorkbenchException) as exc:
        publish_candidate_state_pack(tmp_path, "state-1")
    assert exc.value.code == SYNTHETIC_PROMOTION_BLOCKED

    build_candidate_state_pack(tmp_path, "state-2", "2026-06-04T12:00:00Z", {}, replace(manifest, run_id="state-2"))
    with pytest.raises(WorkbenchException) as exc:
        publish_candidate_state_pack(tmp_path, "state-2", shared_readonly=True)
    assert exc.value.code == SHARED_READONLY_PUBLISH_BLOCKED


def test_failed_publish_preserves_current_hot_state(tmp_path):
    manifest = RunManifest(run_id="state-1", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "state-1", "2026-06-04T12:00:00Z", {"prices": [{"value": 1}]}, manifest)
    publish_candidate_state_pack(tmp_path, "state-1")

    synthetic_manifest = RunManifest(run_id="state-2", created_at="2026-06-04T13:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "state-2", "2026-06-04T13:00:00Z", {"prices": [{"value": 2}]}, synthetic_manifest, synthetic=True)
    with pytest.raises(WorkbenchException):
        publish_candidate_state_pack(tmp_path, "state-2")

    assert HotState(tmp_path).artifacts()["prices"][0]["value"] == 1


def test_agent_tools_are_read_only_and_change_requests_are_reviewed(tmp_path):
    assert_read_only_action("retrieve")
    with pytest.raises(WorkbenchException) as exc:
        assert_read_only_action("publish")
    assert exc.value.code == MUTATING_AGENT_ACTION_BLOCKED

    path = draft_change_request(tmp_path, "CR-9999", "Test learning update", "Capture a reviewed knowledge update")
    assert path.exists()
    assert "approval:" in path.read_text(encoding="utf-8")


def test_pjm_fixture_ingests_observations_and_forecasts(tmp_path):
    fixture = tmp_path / "pjm.csv"
    fixture.write_text(
        "record_type,as_of,source,metric,location_id,delivery_start,delivery_end,value,unit,vintage\n"
        "observation,2026-06-04T12:00:00Z,PJM,load,PJM,2026-06-04T13:00:00Z,2026-06-04T14:00:00Z,1000,MW,\n"
        "forecast,2026-06-04T12:00:00Z,PJM,load_forecast,PJM,2026-06-05T13:00:00Z,2026-06-05T14:00:00Z,1100,MW,2026-06-04T12:00:00Z\n",
        encoding="utf-8",
    )
    observations, forecasts = load_pjm_fundamental_fixture(fixture)
    assert observations[0].source == "PJM"
    assert forecasts[0].forecast_type == "load_forecast"


def test_cli_commands_smoke(tmp_path):
    prices_csv = tmp_path / "marks.csv"
    prices_json = tmp_path / "prices.json"
    prices_csv.write_text(
        "as_of,raw_product,raw_period,price,source\n2026-06-04T12:00:00Z,WH,N26,50,marks_csv\n",
        encoding="utf-8",
    )
    assert main(["validate-registries", "--registries", str(ROOT / "registries"), "--schemas", str(ROOT / "schemas")]) == 0
    assert main(["normalize-prices", "--input", str(prices_csv), "--output", str(prices_json)]) == 0
    assert read_json(prices_json)[0]["index_id"] == "PJM.WH.RT.FULL_LMP.ATC.N26"

    positions_csv = tmp_path / "positions.csv"
    positions_json = tmp_path / "positions.json"
    positions_csv.write_text(
        "as_of,position_id,raw_product,raw_period,raw_quantity,quantity_unit,reference_hours\n"
        "2026-06-04T12:00:00Z,P1,WH,N26,10,MW,10\n",
        encoding="utf-8",
    )
    assert main(["normalize-positions", "--positions", str(positions_csv), "--marks", str(prices_json), "--output", str(positions_json)]) == 0
    assert read_json(positions_json)[0]["derived"]["market_value"] == 5000
