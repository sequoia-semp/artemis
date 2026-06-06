from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.analyst.view_engine import build_view, merge_hot_state_artifacts
from pga_workbench.cache.hot_state import HotState
from pga_workbench.cli import main
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.models import RunManifest
from pga_workbench.serialization import read_json, write_json
from pga_workbench.services.artifact_composition import compose_artifact_payloads
from pga_workbench.state.packs import build_candidate_state_pack, publish_candidate_state_pack


ROOT = Path(__file__).resolve().parents[1]


def _load_artifacts() -> dict:
    return {
        "pjm_load_fundamentals": {"run_id": "load"},
        "summary": "Load summary",
        "drivers": [{"name": "best_actual_load"}],
        "driver_deltas": [{"name": "load_delta"}],
        "forecast_actual_diffs": [{"metric": "PJM.LOAD.FORECAST_ERROR.SEVEN_DAY.HOURLY_MW"}],
        "current_day_view": {
            "actual_load": {"average_mw": 1000},
            "load_forecast": {"average_mw": 950},
        },
        "inputs": {"actual_load": [{"value": 1000}]},
        "source_lineage": [{"artifact": "pjm_load_fundamentals"}],
    }


def _generation_artifacts() -> dict:
    return {
        "pjm_generation_mix": {"run_id": "generation"},
        "summary": "Generation summary",
        "drivers": [{"name": "total_generation_mw"}],
        "current_day_view": {
            "generation_mix": {
                "total_mw": 80000,
                "fuel_count": 3,
            }
        },
        "evidence": [{"artifact": "pjm_generation_mix"}],
        "source_lineage": [{"artifact": "pjm_generation_mix"}],
    }


def _price_shape_artifacts() -> dict:
    return {
        "power_price_shape_rollups": {"run_id": "shapes"},
        "summary": "Price summary",
        "drivers": [{"name": "derived_price_shape_count"}],
        "current_day_view": {
            "price_shapes": {
                "rollup_count": 3,
                "shape_prices": [{"location_id": "WH", "shape": "ATC", "price": 25.0}],
            }
        },
        "price_surface_points": [{"index_id": "PJM.WH.RT.FULL_LMP.ATC.DAY_20260604"}],
        "source_lineage": [{"artifact": "power_price_shape_rollups"}],
    }


def test_compose_artifacts_merges_view_sections_for_hot_state(tmp_path):
    artifacts = compose_artifact_payloads(_load_artifacts(), _generation_artifacts(), _price_shape_artifacts())

    assert "Load summary" in artifacts["summary"]
    assert "Generation summary" in artifacts["summary"]
    assert "Price summary" in artifacts["summary"]
    assert [item["name"] for item in artifacts["drivers"]] == [
        "best_actual_load",
        "total_generation_mw",
        "derived_price_shape_count",
    ]
    assert artifacts["current_day_view"]["actual_load"]["average_mw"] == 1000
    assert artifacts["current_day_view"]["generation_mix"]["total_mw"] == 80000
    assert artifacts["current_day_view"]["price_shapes"]["rollup_count"] == 3
    assert len(artifacts["source_lineage"]) == 3
    assert artifacts["artifact_composition"]["payload_count"] == 3
    assert artifacts["artifact_composition"]["composition_product_keys"] == [
        "pjm_generation_mix",
        "pjm_load_fundamentals",
        "power_price_shape_rollups",
    ]
    assert artifacts["artifact_composition"]["current_day_view_keys"] == [
        "actual_load",
        "generation_mix",
        "load_forecast",
        "price_shapes",
    ]

    manifest = RunManifest(run_id="composed-state", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "composed-state", "2026-06-04T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "composed-state")

    payload = merge_hot_state_artifacts(
        {"as_of": "2026-06-04", "data_environment": "development"},
        HotState(tmp_path).artifacts(),
    )
    view = build_view(ROOT, "current-day", payload)

    assert view["current_day_view"]["actual_load"]["average_mw"] == 1000
    assert view["current_day_view"]["generation_mix"]["fuel_count"] == 3
    assert view["current_day_view"]["price_shapes"]["shape_prices"][0]["shape"] == "ATC"


def test_compose_artifacts_concatenates_shared_series_lists():
    artifacts = compose_artifact_payloads(
        {"price_surface_points": [{"index_id": "hourly"}]},
        {"price_surface_points": [{"index_id": "shape"}]},
    )

    assert [item["index_id"] for item in artifacts["price_surface_points"]] == ["hourly", "shape"]
    assert artifacts["artifact_composition"]["shared_list_counts"]["price_surface_points"] == 2


def test_compose_artifacts_rejects_ambiguous_collisions():
    with pytest.raises(WorkbenchException) as exc:
        compose_artifact_payloads({"pjm_load_fundamentals": {"run_id": "a"}}, {"pjm_load_fundamentals": {"run_id": "b"}})

    assert exc.value.code == "ARTIFACT_COMPOSITION_ERROR"
    assert "Ambiguous artifact key collision" in exc.value.message


def test_compose_artifacts_rejects_reserved_metadata_key():
    with pytest.raises(WorkbenchException) as exc:
        compose_artifact_payloads({"artifact_composition": {"payload_count": 1}})

    assert exc.value.code == "ARTIFACT_COMPOSITION_ERROR"
    assert "reserved key" in exc.value.message


def test_state_pack_rejects_stale_artifact_composition_metadata(tmp_path):
    artifacts = compose_artifact_payloads(_load_artifacts(), _generation_artifacts())
    artifacts["drivers"].append({"name": "late_untracked_driver"})
    manifest = RunManifest(run_id="stale-composition", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")

    with pytest.raises(WorkbenchException) as exc:
        build_candidate_state_pack(tmp_path, "stale-composition", "2026-06-04T12:00:00Z", artifacts, manifest)

    assert exc.value.code == "STATE_PACK_INVALID"
    assert "artifact_composition.shared_list_counts" in exc.value.message


def test_state_pack_rejects_legacy_source_product_key_metadata_mismatch(tmp_path):
    artifacts = compose_artifact_payloads(_load_artifacts(), _generation_artifacts())
    artifacts["artifact_composition"]["source_product_keys"] = ["pjm_load_fundamentals"]
    manifest = RunManifest(run_id="stale-source-product-term", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")

    with pytest.raises(WorkbenchException) as exc:
        build_candidate_state_pack(tmp_path, "stale-source-product-term", "2026-06-04T12:00:00Z", artifacts, manifest)

    assert exc.value.code == "STATE_PACK_INVALID"
    assert "artifact_composition.source_product_keys" in exc.value.message


def test_compose_artifacts_cli_writes_merged_payload(tmp_path):
    load_path = tmp_path / "load.json"
    generation_path = tmp_path / "generation.json"
    output_path = tmp_path / "composed.json"
    write_json(load_path, _load_artifacts())
    write_json(generation_path, _generation_artifacts())

    assert main(["compose-artifacts", "--input", str(load_path), "--input", str(generation_path), "--output", str(output_path)]) == 0

    payload = read_json(output_path)
    assert payload["current_day_view"]["actual_load"]["average_mw"] == 1000
    assert payload["current_day_view"]["generation_mix"]["total_mw"] == 80000
    assert payload["artifact_composition"]["payload_count"] == 2
