from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.analyst.view_engine import build_view, merge_hot_state_artifacts
from pga_workbench.cache.hot_state import HotState
from pga_workbench.cli import _fetch_live_pjm_generation_mix, artemis_main, main
from pga_workbench.data.contracts import DataResult
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.models import RunManifest
from pga_workbench.registry import load_yaml_unique, validate_registries
from pga_workbench.serialization import read_json
from pga_workbench.services.generation_mix import (
    build_pjm_generation_mix_artifacts,
    normalize_pjm_generation_mix_records,
    validate_generation_mix_state,
)
from pga_workbench.state.packs import build_candidate_state_pack, publish_candidate_state_pack


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"


def _load_normalized():
    payload = read_json(FIXTURE)
    return normalize_pjm_generation_mix_records("PJM_GEN_BY_FUEL", payload["feeds"]["gen_by_fuel"], ROOT / "registries", as_of="2026-06-01")


def test_generation_mix_registries_validate_without_warnings():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")
    feeds = load_yaml_unique(ROOT / "registries" / "power_generation_mix_feeds.yaml")
    fuels = load_yaml_unique(ROOT / "registries" / "power_generation_fuels.yaml")

    assert "power_generation_mix_feeds.yaml" in result.validated_files
    assert "power_generation_fuels.yaml" in result.validated_files
    assert result.warnings == []
    assert feeds["PJM_GEN_BY_FUEL"]["data_miner_feed"] == "gen_by_fuel"
    assert fuels["WIND"]["is_renewable"] is True
    assert fuels["STORAGE"]["fuel_family"] == "storage"
    assert fuels["STORAGE"]["source_aliases"]["PJM"] == ["Storage"]


def test_pjm_generation_mix_normalizes_source_fuel_rows():
    observations = _load_normalized()

    assert {item.fuel_id for item in observations} == {"GAS", "NUCLEAR", "WIND"}
    assert all(item.location_id == "PJM_RTO" for item in observations)
    assert all(item.delivery_start == "2026-06-01T04:00:00Z" for item in observations)
    wind = next(item for item in observations if item.fuel_id == "WIND")
    assert wind.is_renewable is True
    assert wind.mw == 7000
    assert wind.fuel_percentage_of_total == 8.75
    assert wind.lineage["data_miner_feed"] == "gen_by_fuel"


def test_pjm_generation_mix_normalizes_live_storage_fuel_label():
    payload = read_json(FIXTURE)
    row = dict(payload["feeds"]["gen_by_fuel"][0])
    row["fuel_type"] = "Storage"
    row["is_renewable"] = False
    row["mw"] = 2200

    observations = normalize_pjm_generation_mix_records("PJM_GEN_BY_FUEL", [row], ROOT / "registries", as_of="2026-06-01")

    assert observations[0].fuel_id == "STORAGE"
    assert observations[0].raw_fuel_type == "Storage"
    assert observations[0].is_renewable is False
    assert observations[0].lineage["fuel_family"] == "storage"


def test_unknown_generation_fuel_fails_closed():
    payload = read_json(FIXTURE)
    row = dict(payload["feeds"]["gen_by_fuel"][0])
    row["fuel_type"] = "Mystery Fuel"

    with pytest.raises(WorkbenchException) as exc:
        normalize_pjm_generation_mix_records("PJM_GEN_BY_FUEL", [row], ROOT / "registries", as_of="2026-06-01")

    assert exc.value.code == "UNKNOWN_GENERATION_FUEL"


def test_renewable_flag_mismatch_fails_closed():
    payload = read_json(FIXTURE)
    row = dict(payload["feeds"]["gen_by_fuel"][2])
    row["is_renewable"] = False

    with pytest.raises(WorkbenchException) as exc:
        normalize_pjm_generation_mix_records("PJM_GEN_BY_FUEL", [row], ROOT / "registries", as_of="2026-06-01")

    assert exc.value.code == "GENERATION_MIX_ERROR"
    assert "Renewable flag mismatch" in exc.value.message


def test_pjm_generation_mix_artifacts_validate_and_publish_to_hot_state(tmp_path):
    observations = _load_normalized()
    artifacts = build_pjm_generation_mix_artifacts(observations, "2026-06-01", run_id="generation-mix-test")

    validate_generation_mix_state(artifacts["pjm_generation_mix"], ROOT / "schemas")
    assert artifacts["pjm_generation_mix"]["lineage"]["total_mw"] == 80000
    assert artifacts["pjm_generation_mix"]["lineage"]["renewable_mw"] == 7000
    assert artifacts["summary"].startswith("PJM generation mix built from source-backed artifacts")
    assert artifacts["current_day_view"]["generation_mix"]["total_mw"] == 80000
    assert artifacts["current_day_view"]["generation_mix"]["renewable_share"] == 0.0875
    assert artifacts["drivers"][0]["name"] == "total_generation_mw"

    manifest = RunManifest(run_id="generation-mix-test", created_at="2026-06-01T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "generation-mix-test", "2026-06-01T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "generation-mix-test")

    hot = HotState(tmp_path).artifacts()
    assert hot["pjm_generation_mix"]["lineage"]["observation_count"] == 3
    assert hot["generation_mix_observations"][0]["source"] == "PJM Data Miner"
    assert hot["current_day_view"]["generation_mix"]["fuel_count"] == 3


def test_generation_mix_hot_state_builds_current_day_view(tmp_path):
    observations = _load_normalized()
    artifacts = build_pjm_generation_mix_artifacts(observations, "2026-06-01", run_id="generation-mix-view-test")
    manifest = RunManifest(run_id="generation-mix-view-test", created_at="2026-06-01T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "generation-mix-view-test", "2026-06-01T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "generation-mix-view-test")

    payload = merge_hot_state_artifacts(
        {"as_of": "2026-06-01", "data_environment": "development"},
        HotState(tmp_path).artifacts(),
    )
    view = build_view(ROOT, "current-day", payload)

    assert view["summary"].startswith("PJM generation mix built from source-backed artifacts")
    assert view["drivers"][0]["name"] == "total_generation_mw"
    assert view["current_day_view"]["generation_mix"]["total_mw"] == 80000
    assert view["current_day_view"]["generation_mix"]["top_fuels"][0]["fuel_id"] == "GAS"
    assert view["evidence"][0]["artifact"] == "pjm_generation_mix"


def test_pjm_generation_mix_cli_builds_artifacts_from_fixture(tmp_path):
    output = tmp_path / "pjm_generation_mix.json"

    assert main(
        [
            "build-pjm-generation-mix",
            "--input",
            str(FIXTURE),
            "--as-of",
            "2026-06-01",
            "--start",
            "2026-06-01",
            "--end",
            "2026-06-01",
            "--output",
            str(output),
        ]
    ) == 0

    assert read_json(output)["pjm_generation_mix"]["lineage"]["fuel_ids"] == ["GAS", "NUCLEAR", "WIND"]


def test_artemis_pjm_generation_mix_cli_alias_builds_artifacts_from_fixture(tmp_path):
    output = tmp_path / "pjm_generation_mix.json"

    assert artemis_main(
        [
            "analyst",
            "fundamentals",
            "build-pjm-generation-mix",
            "--input",
            str(FIXTURE),
            "--as-of",
            "2026-06-01",
            "--start",
            "2026-06-01",
            "--end",
            "2026-06-01",
            "--output",
            str(output),
        ]
    ) == 0

    assert read_json(output)["pjm_generation_mix"]["lineage"]["observation_count"] == 3


def test_live_pjm_generation_mix_fetch_uses_bounded_query_request_records(monkeypatch):
    from argparse import Namespace

    seen = []

    def fake_fetch(self, request):
        seen.append(dict(request.parameters))
        return DataResult(source="PJM Data Miner", contract=request.contract, data_environment="test", records=[], lineage={})

    monkeypatch.setattr("pga_workbench.cli.load_artemis_config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr("pga_workbench.cli.PjmDataMinerConnector.fetch", fake_fetch)

    args = Namespace(
        repo_root=".",
        base_url="https://example.test",
        as_of="2026-06-01",
        start="2026-06-01",
        end="2026-06-01",
        row_count=24,
        no_paginate=True,
        max_pages=1,
    )

    observations = _fetch_live_pjm_generation_mix(args, ROOT / "registries")

    assert observations == []
    assert seen[0]["query_request"]["request_id"] == "PJM_DATAMINER_GENERATION_MIX_BOUNDED_INTERVAL.PJM_GEN_BY_FUEL.2026-06-01.2026-06-01"
    assert seen[0]["query_execution_summary"]["plan_id"] == "PJM_DATAMINER_GENERATION_MIX_BOUNDED_INTERVAL"
    assert seen[0]["query_execution_summary"]["contains_secret_values"] is False
    assert seen[0]["query"]["datetime_beginning_utc"] == "2026-06-01 00:00:00 to 2026-06-01 23:59:59"
