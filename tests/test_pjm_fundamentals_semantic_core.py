from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.analyst.view_engine import build_view, merge_hot_state_artifacts
from pga_workbench.cache.hot_state import HotState
from pga_workbench.cli import _fetch_live_pjm_load, _fetch_live_pjm_load_with_manifest, artemis_main, main
from pga_workbench.data.contracts import DataResult
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.models import RunManifest
from pga_workbench.registry import validate_registries
from pga_workbench.serialization import read_json
from pga_workbench.services.fundamentals import (
    build_pjm_load_artifacts,
    load_pjm_fundamental_feeds,
    normalize_pjm_fundamental_records,
    normalize_pjm_load_area,
    validate_fundamental_state,
)
from pga_workbench.state.packs import build_candidate_state_pack, publish_candidate_state_pack


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"


def _load_normalized():
    payload = read_json(FIXTURE)
    observations = []
    forecasts = []
    for feed_id, rows in payload["feeds"].items():
        obs, fcst = normalize_pjm_fundamental_records(feed_id, rows, ROOT / "registries", as_of="2026-06-04")
        observations.extend(obs)
        forecasts.extend(fcst)
    return observations, forecasts


def test_pjm_fundamental_feed_and_area_registries_validate():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")

    assert "pjm_fundamental_feeds.yaml" in result.validated_files
    assert "pjm_load_areas.yaml" in result.validated_files
    assert result.warnings == []
    assert normalize_pjm_load_area("RTO_COMBINED", ROOT / "registries") == "PJM_RTO"


def test_pjm_preliminary_load_contract_is_zonal_source_specific():
    feeds = load_pjm_fundamental_feeds(ROOT / "registries")

    assert feeds["hrl_load_metered"]["default_area_filter"] == "RTO"
    assert feeds["hrl_load_prelim"]["area_columns"] == ["load_area"]
    assert feeds["hrl_load_prelim"].get("default_area_filter") is None


def test_pjm_fundamental_normalization_preserves_products_and_windows():
    observations, forecasts = _load_normalized()

    assert {item.metric for item in observations} == {
        "PJM.LOAD.ACTUAL.METERED.HOURLY_MW",
        "PJM.LOAD.ACTUAL.PRELIMINARY.HOURLY_MW",
    }
    assert {item.forecast_type for item in forecasts} == {
        "PJM.LOAD.FORECAST.SEVEN_DAY.LATEST.HOURLY_MW",
        "PJM.LOAD.FORECAST.SEVEN_DAY.REVISION.HOURLY_MW",
    }
    revision = next(item for item in forecasts if item.forecast_type.endswith("REVISION.HOURLY_MW"))
    assert revision.delivery_end == "2026-06-04T14:00:00Z"
    assert all(item.location_id == "PJM_RTO" for item in [*observations, *forecasts])


def test_pjm_fundamental_state_derives_best_series_errors_and_gaps():
    observations, forecasts = _load_normalized()
    artifacts = build_pjm_load_artifacts(observations, forecasts, "2026-06-04", run_id="test-pjm-load")
    state = artifacts["pjm_load_fundamentals"]

    validate_fundamental_state(state, ROOT / "schemas")
    actuals = state["best_series"]["PJM.LOAD.ACTUAL.HOURLY_MW"]
    assert len(actuals) == 1
    assert actuals[0]["value"] == 1000
    assert actuals[0]["lineage"]["best_series_source_metric"] == "PJM.LOAD.ACTUAL.METERED.HOURLY_MW"
    assert state["derived"][0]["value"] == 50
    assert "PJM.LOAD.FORECAST.SEVEN_DAY.LATEST.HOURLY_MW" in state["best_series"]
    assert "PJM.LOAD.FORECAST.SEVEN_DAY.REVISION.HOURLY_MW" in state["best_series"]
    assert {gap["date"] for gap in state["gaps"]} >= {"2026-06-06", "2026-06-18"}
    assert "2 latest forecast intervals" in artifacts["summary"]
    assert artifacts["drivers"][0]["name"] == "best_actual_load"
    assert artifacts["drivers"][1]["coverage"]["count"] == 2
    assert artifacts["driver_deltas"][0]["value"] == 50
    assert artifacts["current_day_view"]["actual_load"]["average_mw"] == 1000


def test_unknown_pjm_load_area_fails_closed():
    payload = read_json(FIXTURE)
    row = dict(payload["feeds"]["load_frcstd_7_day"][0])
    row["forecast_area"] = "UNKNOWN_AREA"

    with pytest.raises(WorkbenchException):
        normalize_pjm_fundamental_records("load_frcstd_7_day", [row], ROOT / "registries", as_of="2026-06-04")


def test_pjm_load_cli_builds_artifacts_from_fixture(tmp_path):
    output = tmp_path / "pjm_load_artifacts.json"

    assert main(
        [
            "build-pjm-load-fundamentals",
            "--input",
            str(FIXTURE),
            "--as-of",
            "2026-06-04",
            "--start",
            "2026-06-04",
            "--end",
            "2026-06-18",
            "--output",
            str(output),
        ]
    ) == 0
    artifacts = read_json(output)

    assert artifacts["pjm_load_fundamentals"]["derived"][0]["value"] == 50
    assert artifacts["inputs"]["actual_load"][0]["value"] == 1000


def test_artemis_pjm_load_cli_alias_builds_artifacts_from_fixture(tmp_path):
    output = tmp_path / "pjm_load_artifacts.json"

    assert artemis_main(
        [
            "analyst",
            "fundamentals",
            "build-pjm-load",
            "--input",
            str(FIXTURE),
            "--as-of",
            "2026-06-04",
            "--start",
            "2026-06-04",
            "--end",
            "2026-06-18",
            "--output",
            str(output),
        ]
    ) == 0
    assert read_json(output)["pjm_load_fundamentals"]["lineage"]["latest_forecast_count"] == 2


def test_artemis_pjm_load_cli_parses_bounded_live_flags():
    from pga_workbench.cli import build_artemis_parser

    parser = build_artemis_parser()
    args = parser.parse_args(
        [
            "analyst",
            "fundamentals",
            "build-pjm-load",
            "--live",
            "--feed",
            "load_frcstd_7_day",
            "--as-of",
            "2026-06-06",
            "--start",
            "2026-06-06",
            "--end",
            "2026-06-06",
            "--output",
            "/tmp/pjm.json",
            "--row-count",
            "24",
            "--max-pages",
            "1",
            "--no-paginate",
        ]
    )

    assert args.row_count == 24
    assert args.max_pages == 1
    assert args.no_paginate is True


def test_live_pjm_load_fetch_uses_bounded_query_request_records(monkeypatch):
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
        area=None,
        feed=["load_frcstd_7_day"],
        row_count=24,
        no_paginate=True,
        max_pages=1,
    )

    observations, forecasts, manifests = _fetch_live_pjm_load_with_manifest(args, ROOT / "registries")

    assert observations == []
    assert forecasts == []
    assert manifests[0]["source_surface"] == "load"
    assert manifests[0]["registry_feed_id"] == "load_frcstd_7_day"
    assert manifests[0]["query_plan_id"] == "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"
    assert manifests[0]["contains_raw_records"] is False
    assert seen[0]["query_request"]["request_id"] == "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL.load_frcstd_7_day.2026-06-01.2026-06-01"
    assert seen[0]["query_execution_summary"]["plan_id"] == "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"
    assert seen[0]["query_execution_summary"]["contains_secret_values"] is False
    assert seen[0]["query"]["forecast_area"] == "RTO_COMBINED"


def test_pjm_load_artifacts_publish_to_hot_state_and_feed_views(tmp_path):
    observations, forecasts = _load_normalized()
    artifacts = build_pjm_load_artifacts(observations, forecasts, "2026-06-04", run_id="state-1")
    manifest = RunManifest(run_id="state-1", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "state-1", "2026-06-04T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "state-1")

    hot_artifacts = HotState(tmp_path).artifacts()
    payload = merge_hot_state_artifacts({"as_of": "2026-06-04", "data_environment": "development"}, hot_artifacts)
    view = build_view(ROOT, "fourteen-day-fundamentals", payload)

    assert view["summary"].startswith("PJM load fundamentals built from source-backed artifacts")
    assert view["drivers"][1]["name"] == "latest_load_forecast"
    assert view["forecast_actual_diffs"][0]["value"] == 50
    assert view["current_day_view"]["actual_load"]["average_mw"] == 1000
    assert view["prior_day_retrospective"]["forecast_error"]["largest_abs_error"]["value"] == 50
    assert view["fourteen_day_outlook"]["gaps"][0]["reason"] == "no_source_backed_forecast_for_day"


def test_pjm_load_artifacts_feed_current_and_prior_view_templates(tmp_path):
    observations, forecasts = _load_normalized()
    artifacts = build_pjm_load_artifacts(observations, forecasts, "2026-06-04", run_id="state-1")
    manifest = RunManifest(run_id="state-1", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "state-1", "2026-06-04T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "state-1")

    payload = merge_hot_state_artifacts({"as_of": "2026-06-04", "data_environment": "development"}, HotState(tmp_path).artifacts())
    current = build_view(ROOT, "current-day", payload)
    prior = build_view(ROOT, "prior-day-retrospective", payload)

    assert current["current_day_view"]["load_forecast"]["average_mw"] == 950
    assert prior["prior_day_retrospective"]["forecast_error"]["largest_abs_error"]["value"] == 50
