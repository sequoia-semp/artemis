from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.cache.hot_state import HOT_STATE_INVALID, HotState
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.models import PriceSurfacePoint, RunManifest
from pga_workbench.serialization import to_plain
from pga_workbench.state.packs import build_candidate_state_pack, publish_candidate_state_pack


def _point(
    *,
    index_id: str,
    location_id: str = "WH",
    source_role: str = "authoritative_iso_publication",
    lineage: dict | None = None,
) -> dict:
    return to_plain(
        PriceSurfacePoint(
            as_of="2026-06-04T12:00:00Z",
            index_id=index_id,
            location_id=location_id,
            commodity="power",
            period_id="HOUR_20260604T130000Z",
            price=35.0,
            quote_unit="USD_per_MWh",
            source="PJM Data Miner",
            source_role=source_role,
            lineage=lineage or {},
        )
    )


def _publish_artifacts(tmp_path: Path, artifacts: dict) -> HotState:
    manifest = RunManifest(run_id="price-query-state", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "price-query-state", "2026-06-04T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "price-query-state")
    return HotState(tmp_path)


def test_hot_state_price_surface_point_queries_separate_source_and_derived_shapes(tmp_path):
    hot = _publish_artifacts(
        tmp_path,
        {
            "price_surface_points": [
                _point(index_id="PJM.WH.RT.FULL_LMP.HOURLY.HOUR_20260604T130000Z", lineage={"source_feed_id": "PJM_RT_HOURLY_LMP"}),
                _point(
                    index_id="PJM.WH.RT.FULL_LMP.ATC.DAY_20260604",
                    source_role="derived_from_authoritative_iso_publication",
                    lineage={"source_artifact": "power_price_shape_rollups", "shape": "ATC"},
                ),
                _point(index_id="PJM.AD.RT.FULL_LMP.HOURLY.HOUR_20260604T130000Z", location_id="AD", lineage={"source_feed_id": "PJM_RT_HOURLY_LMP"}),
            ],
        },
    )

    assert [point.index_id for point in hot.price_surface_points(location_id="WH")] == [
        "PJM.WH.RT.FULL_LMP.HOURLY.HOUR_20260604T130000Z",
        "PJM.WH.RT.FULL_LMP.ATC.DAY_20260604",
    ]
    assert [point.index_id for point in hot.source_price_points()] == [
        "PJM.WH.RT.FULL_LMP.HOURLY.HOUR_20260604T130000Z",
        "PJM.AD.RT.FULL_LMP.HOURLY.HOUR_20260604T130000Z",
    ]
    assert [point.index_id for point in hot.source_price_points(location_id="WH")] == [
        "PJM.WH.RT.FULL_LMP.HOURLY.HOUR_20260604T130000Z"
    ]
    assert [point.index_id for point in hot.derived_price_shape_points()] == ["PJM.WH.RT.FULL_LMP.ATC.DAY_20260604"]


def test_hot_state_price_surface_point_query_rejects_non_list_payload(tmp_path):
    hot = _publish_artifacts(tmp_path, {"price_surface_points": {"bad": "payload"}})

    with pytest.raises(WorkbenchException) as exc:
        hot.price_surface_points()

    assert exc.value.code == HOT_STATE_INVALID
    assert "price_surface_points must be a list" in exc.value.message
