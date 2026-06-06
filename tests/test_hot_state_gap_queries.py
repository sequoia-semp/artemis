from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pga_workbench.cache.hot_state import HOT_STATE_INVALID, HotState
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.models import PriceSurfacePoint, RunManifest
from pga_workbench.serialization import read_json
from pga_workbench.services.fundamentals import build_pjm_load_artifacts, normalize_pjm_fundamental_records
from pga_workbench.services.power_price_shapes import build_power_price_shape_artifacts
from pga_workbench.state.packs import build_candidate_state_pack, publish_candidate_state_pack


ROOT = Path(__file__).resolve().parents[1]
LOAD_FIXTURE = ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"


def _publish_artifacts(tmp_path: Path, artifacts: dict) -> HotState:
    manifest = RunManifest(run_id="gap-query-state", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "gap-query-state", "2026-06-04T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "gap-query-state")
    return HotState(tmp_path)


def _load_artifacts() -> dict:
    payload = read_json(LOAD_FIXTURE)
    observations = []
    forecasts = []
    for feed_id, rows in payload["feeds"].items():
        obs, fcst = normalize_pjm_fundamental_records(feed_id, rows, ROOT / "registries", as_of="2026-06-04")
        observations.extend(obs)
        forecasts.extend(fcst)
    return build_pjm_load_artifacts(observations, forecasts, "2026-06-04", run_id="load-gap-state")


def _hourly_points(count: int = 8) -> list[PriceSurfacePoint]:
    points: list[PriceSurfacePoint] = []
    base = datetime.fromisoformat("2026-06-01T00:00:00")
    for hour in range(count):
        start = base + timedelta(hours=hour)
        period_id = f"HOUR_{start:%Y%m%dT%H%M%SZ}"
        points.append(
            PriceSurfacePoint(
                as_of="2026-06-01T12:00:00Z",
                index_id=f"PJM.WH.RT.FULL_LMP.HOURLY.{period_id}",
                location_id="WH",
                commodity="power",
                period_id=period_id,
                price=float(hour + 1),
                quote_unit="USD_per_MWh",
                source="PJM Data Miner",
                source_role="authoritative_iso_publication",
                lineage={
                    "delivery_start_ept": start.isoformat(),
                    "price_component": "FULL_LMP",
                    "market_run": "RT",
                },
            )
        )
    return points


def test_hot_state_fundamental_gap_queries_return_explicit_forecast_gaps(tmp_path):
    hot = _publish_artifacts(tmp_path, _load_artifacts())

    gaps = hot.fundamental_gaps(location_id="PJM_RTO", reason="no_source_backed_forecast_for_day")

    assert gaps
    assert {gap["source_artifact"] for gap in gaps} == {"pjm_load_fundamentals"}
    assert {gap["reason"] for gap in gaps} == {"no_source_backed_forecast_for_day"}
    assert {gap["date"] for gap in gaps} >= {"2026-06-06", "2026-06-18"}


def test_hot_state_price_shape_gap_queries_return_derived_shape_gaps(tmp_path):
    artifacts = build_power_price_shape_artifacts(_hourly_points(), ROOT / "registries", "2026-06-01", run_id="shape-gap-state")
    hot = _publish_artifacts(tmp_path, artifacts)

    gaps = hot.price_shape_gaps(location_id="WH", reason="missing_hourly_source_prices")

    assert gaps
    assert {gap["source_artifact"] for gap in gaps} == {"power_price_shape_rollups"}
    assert {gap["reason"] for gap in gaps} == {"missing_hourly_source_prices"}
    assert any(gap["observed_hours"] < gap["expected_hours"] for gap in gaps)


def test_hot_state_gap_query_rejects_invalid_gap_payload(tmp_path):
    hot = _publish_artifacts(tmp_path, {"pjm_load_fundamentals": {"gaps": {"bad": "payload"}}})

    with pytest.raises(WorkbenchException) as exc:
        hot.fundamental_gaps()

    assert exc.value.code == HOT_STATE_INVALID
    assert "gaps must be a list" in exc.value.message
