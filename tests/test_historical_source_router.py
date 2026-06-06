from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.services.historical_source_router import (
    HISTORICAL_SOURCE_ROUTER_ERROR,
    build_historical_source_request_plan,
)


ROOT = Path(__file__).resolve().parents[1]


def test_historical_router_builds_pjm_lmp_requests_from_retention_policy():
    plan = build_historical_source_request_plan(
        ROOT / "registries",
        "pjm_power_prices",
        as_of="2026-06-06T12:00:00Z",
        pnode_ids=[51288],
        price_feed_ids=["PJM_RT_HOURLY_LMP"],
        row_count=24,
        account_class="member",
        paginate=False,
    )

    assert plan["history_start"] == "2026-05-07"
    assert plan["history_end"] == "2026-06-06"
    assert plan["derived_view_windows_days"] == [1, 5, 10, 30]
    assert plan["approved_query_plan_ids"] == ["PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS"]
    assert plan["row_version_policy"] == "current_row_filter_required"
    assert plan["query_plans"][0]["plan_id"] == "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS"
    assert plan["request_count"] == 32
    assert plan["requests"][0]["request_kind"] == "metadata"
    assert plan["requests"][1]["window_start"] == "2026-05-07"
    assert plan["requests"][-1]["window_end"] == "2026-06-06"
    assert plan["contains_secret_values"] is False


def test_historical_router_requires_pnodes_for_pjm_lmp_history():
    with pytest.raises(WorkbenchException) as exc:
        build_historical_source_request_plan(
            ROOT / "registries",
            "pjm_power_prices",
            as_of="2026-06-06",
        )

    assert exc.value.code == HISTORICAL_SOURCE_ROUTER_ERROR
    assert "pnode_ids" in exc.value.message


def test_historical_router_defaults_pjm_load_to_approved_forecast_feeds_only():
    plan = build_historical_source_request_plan(
        ROOT / "registries",
        "pjm_load_fundamentals",
        as_of="2026-06-06",
        row_count=24,
        account_class="member",
        paginate=False,
    )

    assert plan["history_start"] == "2026-05-23"
    assert plan["history_end"] == "2026-06-06"
    assert plan["approved_query_plan_ids"] == ["PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"]
    assert {item["registry_feed_id"] for item in plan["requests"]} == {"load_frcstd_7_day", "load_frcstd_hist"}
    assert "hrl_load_metered" not in {item["registry_feed_id"] for item in plan["requests"]}
    assert "hrl_load_prelim" not in {item["registry_feed_id"] for item in plan["requests"]}


def test_historical_router_builds_generation_mix_requests_from_retention_policy():
    plan = build_historical_source_request_plan(
        ROOT / "registries",
        "pjm_generation_mix",
        as_of="2026-06-06",
        row_count=24,
        account_class="member",
        paginate=False,
    )

    assert plan["history_start"] == "2026-05-23"
    assert plan["history_end"] == "2026-06-06"
    assert plan["approved_query_plan_ids"] == ["PJM_DATAMINER_GENERATION_MIX_BOUNDED_INTERVAL"]
    assert plan["request_count"] == 1
    assert plan["requests"][0]["registry_feed_id"] == "PJM_GEN_BY_FUEL"


def test_historical_router_rejects_non_source_restorable_products():
    with pytest.raises(WorkbenchException) as exc:
        build_historical_source_request_plan(
            ROOT / "registries",
            "power_price_shape_rollups",
            as_of="2026-06-06",
        )

    assert exc.value.code == HISTORICAL_SOURCE_ROUTER_ERROR
    assert "not source-restorable" in exc.value.message
