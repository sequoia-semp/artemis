from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.cache.hot_state import HOT_STATE_INVALID, HotState
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.models import RunManifest
from pga_workbench.serialization import read_json
from pga_workbench.services.fundamentals import build_pjm_load_artifacts, normalize_pjm_fundamental_records
from pga_workbench.services.generation_mix import build_pjm_generation_mix_artifacts, normalize_pjm_generation_mix_records
from pga_workbench.state.packs import build_candidate_state_pack, publish_candidate_state_pack


ROOT = Path(__file__).resolve().parents[1]
LOAD_FIXTURE = ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"
GENERATION_FIXTURE = ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"


def _load_artifacts() -> dict:
    payload = read_json(LOAD_FIXTURE)
    observations = []
    forecasts = []
    for feed_id, rows in payload["feeds"].items():
        obs, fcst = normalize_pjm_fundamental_records(feed_id, rows, ROOT / "registries", as_of="2026-06-04")
        observations.extend(obs)
        forecasts.extend(fcst)
    return build_pjm_load_artifacts(observations, forecasts, "2026-06-04", run_id="load-query-state")


def _generation_artifacts() -> dict:
    payload = read_json(GENERATION_FIXTURE)
    observations = normalize_pjm_generation_mix_records("PJM_GEN_BY_FUEL", payload["feeds"]["gen_by_fuel"], ROOT / "registries", as_of="2026-06-01")
    return build_pjm_generation_mix_artifacts(observations, "2026-06-01", run_id="generation-query-state")


def _publish_artifacts(tmp_path: Path, artifacts: dict) -> HotState:
    manifest = RunManifest(run_id="fundamental-query-state", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "fundamental-query-state", "2026-06-04T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "fundamental-query-state")
    return HotState(tmp_path)


def test_hot_state_fundamental_queries_separate_source_products_from_best_series(tmp_path):
    hot = _publish_artifacts(tmp_path, _load_artifacts())

    source_actuals = hot.fundamental_source_records(product_id="PJM.LOAD.ACTUAL.METERED.HOURLY_MW")
    best_actuals = hot.fundamental_best_series_records(metric_id="PJM.LOAD.ACTUAL.HOURLY_MW")
    revisions = hot.fundamental_source_records(product_id="PJM.LOAD.FORECAST.SEVEN_DAY.REVISION.HOURLY_MW")

    assert len(source_actuals) == 1
    assert source_actuals[0]["metric"] == "PJM.LOAD.ACTUAL.METERED.HOURLY_MW"
    assert source_actuals[0]["source_product_id"] == "PJM.LOAD.ACTUAL.METERED.HOURLY_MW"
    assert len(best_actuals) == 1
    assert best_actuals[0]["metric"] == "PJM.LOAD.ACTUAL.HOURLY_MW"
    assert best_actuals[0]["best_series_id"] == "PJM.LOAD.ACTUAL.HOURLY_MW"
    assert best_actuals[0]["lineage"]["best_series_source_metric"] == "PJM.LOAD.ACTUAL.METERED.HOURLY_MW"
    assert len(revisions) == 1
    assert revisions[0]["forecast_type"] == "PJM.LOAD.FORECAST.SEVEN_DAY.REVISION.HOURLY_MW"


def test_hot_state_generation_mix_query_returns_typed_observations(tmp_path):
    hot = _publish_artifacts(tmp_path, _generation_artifacts())

    wind = hot.generation_mix_observations(location_id="PJM_RTO", fuel_id="WIND")

    assert len(wind) == 1
    assert wind[0].source == "PJM Data Miner"
    assert wind[0].mw == 7000
    assert wind[0].lineage["data_miner_feed"] == "gen_by_fuel"


def test_hot_state_fundamental_query_rejects_invalid_source_products(tmp_path):
    hot = _publish_artifacts(tmp_path, {"pjm_load_fundamentals": {"source_products": []}})

    with pytest.raises(WorkbenchException) as exc:
        hot.fundamental_source_records()

    assert exc.value.code == HOT_STATE_INVALID
    assert "source_products must be a mapping" in exc.value.message
