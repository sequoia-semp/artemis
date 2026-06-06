from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.registry import validate_registries
from pga_workbench.services.source_query_plans import (
    SOURCE_QUERY_PLAN_ERROR,
    build_pjm_generation_mix_query_requests,
    build_pjm_hourly_lmp_query_requests,
    build_pjm_load_query_requests,
    plan_pjm_hourly_lmp_queries,
    summarize_source_query_requests,
    validate_power_system_source_query_plan_references,
)


ROOT = Path(__file__).resolve().parents[1]


def test_source_query_plan_registry_validates_without_warnings():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")

    assert "power_system_source_query_plans.yaml" in result.validated_files
    assert result.warnings == []


def test_source_query_plan_references_resolve_to_publications_and_feed_descriptors():
    resolved = validate_power_system_source_query_plan_references(ROOT / "registries")

    assert resolved["PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"]["publication_id"] == "PJM_DATAMINER_LOAD_FORECASTS"
    assert resolved["PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"]["feed_publications"]["hrl_load_metered"] == [
        "PJM_DATAMINER_LOAD_ACTUALS"
    ]
    assert resolved["PJM_DATAMINER_FIVE_MINUTE_RT_LMP_CANDIDATE_DAILY_CHUNKS"]["publication_id"] == "PJM_DATAMINER_FIVE_MINUTE_RT_LMP"
    assert resolved["PJM_DATAMINER_FIVE_MINUTE_RT_LMP_CANDIDATE_DAILY_CHUNKS"]["feed_ids"] == ["PJM_RT_FIVE_MINUTE_LMP"]
    assert resolved["PJM_DATAMINER_GENERATION_MIX_BOUNDED_INTERVAL"]["feed_publications"]["PJM_GEN_BY_FUEL"] == [
        "PJM_DATAMINER_GENERATION_BY_FUEL"
    ]


def test_source_query_plan_unknown_publication_fails_closed(tmp_path):
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in [
        "pjm_fundamental_feeds.yaml",
        "power_system_price_feeds.yaml",
        "power_generation_mix_feeds.yaml",
        "power_system_operational_event_feeds.yaml",
        "power_system_source_catalog.yaml",
        "power_system_source_query_plans.yaml",
    ]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")

    plans = yaml.safe_load((registry_dir / "power_system_source_query_plans.yaml").read_text(encoding="utf-8"))
    plans["PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"]["publication_id"] = "PJM_UNKNOWN_PUBLICATION"
    (registry_dir / "power_system_source_query_plans.yaml").write_text(yaml.safe_dump(plans, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_source_query_plan_references(registry_dir)

    assert exc.value.code == SOURCE_QUERY_PLAN_ERROR
    assert "unknown source publication" in exc.value.message


def test_source_query_plan_unknown_feed_descriptor_fails_closed(tmp_path):
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in [
        "pjm_fundamental_feeds.yaml",
        "power_system_price_feeds.yaml",
        "power_generation_mix_feeds.yaml",
        "power_system_operational_event_feeds.yaml",
        "power_system_source_catalog.yaml",
        "power_system_source_query_plans.yaml",
    ]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")

    plans = yaml.safe_load((registry_dir / "power_system_source_query_plans.yaml").read_text(encoding="utf-8"))
    plans["PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"]["applies_to_feed_ids"].append("PJM_UNKNOWN_FEED")
    (registry_dir / "power_system_source_query_plans.yaml").write_text(yaml.safe_dump(plans, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_source_query_plan_references(registry_dir)

    assert exc.value.code == SOURCE_QUERY_PLAN_ERROR
    assert "unknown feed descriptors" in exc.value.message


def test_pjm_hourly_lmp_query_plan_chunks_days_and_counts_requests():
    plan = plan_pjm_hourly_lmp_queries(
        ROOT / "registries",
        "2026-06-01",
        "2026-06-02",
        ["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"],
        pnode_count=1,
    )

    assert [(window.start, window.end) for window in plan.windows] == [
        ("2026-06-01", "2026-06-01"),
        ("2026-06-02", "2026-06-02"),
    ]
    assert plan.planned_request_count == 5
    assert plan.max_connections_per_minute == 6
    assert plan.lineage["metadata_requests_per_pnode"] == 1


def test_pjm_hourly_lmp_query_plan_rejects_non_member_over_budget_plan():
    with pytest.raises(WorkbenchException) as exc:
        plan_pjm_hourly_lmp_queries(
            ROOT / "registries",
            "2026-06-01",
            "2026-06-03",
            ["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"],
            pnode_count=1,
        )

    assert exc.value.code == SOURCE_QUERY_PLAN_ERROR
    assert "requires 7 requests" in exc.value.message


def test_pjm_hourly_lmp_query_plan_allows_member_budget_for_larger_plan():
    plan = plan_pjm_hourly_lmp_queries(
        ROOT / "registries",
        "2026-06-01",
        "2026-06-03",
        ["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"],
        pnode_count=1,
        account_class="member",
    )

    assert len(plan.windows) == 3
    assert plan.planned_request_count == 7
    assert plan.max_connections_per_minute == 600


def test_pjm_hourly_lmp_query_requests_are_deterministic_and_executable():
    plan, requests = build_pjm_hourly_lmp_query_requests(
        ROOT / "registries",
        "2026-06-01",
        "2026-06-02",
        ["PJM_RT_HOURLY_LMP"],
        [51288],
        row_count=24,
        paginate=False,
        max_pages=1,
    )

    assert plan.planned_request_count == len(requests) == 3
    assert [item.request_id for item in requests] == [
        "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS.PNODE.51288",
        "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS.PJM_RT_HOURLY_LMP.51288.2026-06-01",
        "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS.PJM_RT_HOURLY_LMP.51288.2026-06-02",
    ]
    assert requests[0].request_kind == "metadata"
    assert requests[0].query["fields"].startswith("pnode_id,pnode_name")
    lmp_request = requests[1]
    assert lmp_request.request_kind == "source_rows"
    assert lmp_request.query["datetime_beginning_utc"] == "2026-06-01 00:00:00 to 2026-06-01 23:59:59"
    assert lmp_request.query["row_is_current"] == 1
    assert "total_lmp_rt" in lmp_request.query["fields"]
    assert lmp_request.paginate is False
    assert lmp_request.query_plan["plan_id"] == "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS"


def test_pjm_hourly_lmp_query_request_summary_is_redacted():
    plan, requests = build_pjm_hourly_lmp_query_requests(
        ROOT / "registries",
        "2026-06-01",
        "2026-06-01",
        ["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"],
        [51288],
        row_count=24,
    )
    summary = summarize_source_query_requests(plan, requests)

    assert summary == {
        "plan_id": "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS",
        "planned_request_count": 3,
        "built_request_count": 3,
        "account_class": "non_member",
        "max_connections_per_minute": 6,
        "request_kinds": {"metadata": 1, "source_rows": 2},
        "registry_feed_ids": ["PJM_DA_HOURLY_LMP", "PJM_PNODE", "PJM_RT_HOURLY_LMP"],
        "pnode_ids": [51288],
        "date_windows": [{"start": "2026-06-01", "end": "2026-06-01"}],
        "contains_secret_values": False,
    }


def test_pjm_hourly_lmp_query_request_count_must_match_budget():
    with pytest.raises(WorkbenchException) as exc:
        build_pjm_hourly_lmp_query_requests(
            ROOT / "registries",
            "2026-06-01",
            "2026-06-01",
            ["PJM_RT_HOURLY_LMP"],
            [51288],
            row_count=0,
        )

    assert exc.value.code == SOURCE_QUERY_PLAN_ERROR
    assert "row_count must be positive" in exc.value.message


def test_pjm_load_query_requests_are_bounded_interval_records():
    plan, requests = build_pjm_load_query_requests(
        ROOT / "registries",
        "2026-06-01",
        "2026-06-01",
        ["load_frcstd_7_day"],
        area=None,
        row_count=24,
        paginate=False,
        max_pages=1,
    )

    assert plan.plan_id == "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"
    assert plan.lineage["publication_id"] == "PJM_DATAMINER_LOAD_FORECASTS"
    assert plan.lineage["max_days_per_request"] == 10000
    assert plan.planned_request_count == len(requests) == 1
    request = requests[0]
    assert request.request_id == "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL.load_frcstd_7_day.2026-06-01.2026-06-01"
    assert request.registry_feed_id == "load_frcstd_7_day"
    assert request.data_miner_feed == "load_frcstd_7_day"
    assert request.pnode_id is None
    assert request.query["forecast_datetime_beginning_utc"] == "2026-06-01 00:00:00 to 2026-06-01 23:59:59"
    assert request.query["forecast_area"] == "RTO_COMBINED"
    assert request.paginate is False
    summary = summarize_source_query_requests(plan, requests)
    assert summary["request_kinds"] == {"source_rows": 1}
    assert summary["pnode_ids"] == []
    assert summary["contains_secret_values"] is False


def test_pjm_generation_mix_query_requests_are_bounded_interval_records():
    plan, requests = build_pjm_generation_mix_query_requests(
        ROOT / "registries",
        "2026-06-01",
        "2026-06-01",
        row_count=24,
        paginate=False,
        max_pages=1,
    )

    assert plan.plan_id == "PJM_DATAMINER_GENERATION_MIX_BOUNDED_INTERVAL"
    assert plan.lineage["publication_id"] == "PJM_DATAMINER_GENERATION_BY_FUEL"
    assert plan.lineage["max_days_per_request"] == 10000
    assert plan.planned_request_count == len(requests) == 1
    request = requests[0]
    assert request.request_id == "PJM_DATAMINER_GENERATION_MIX_BOUNDED_INTERVAL.PJM_GEN_BY_FUEL.2026-06-01.2026-06-01"
    assert request.registry_feed_id == "PJM_GEN_BY_FUEL"
    assert request.data_miner_feed == "gen_by_fuel"
    assert request.query["datetime_beginning_utc"] == "2026-06-01 00:00:00 to 2026-06-01 23:59:59"
    assert "fuel_type" in request.query["fields"]


def test_bounded_interval_query_requests_enforce_row_count_policy():
    with pytest.raises(WorkbenchException) as exc:
        build_pjm_load_query_requests(
            ROOT / "registries",
            "2026-06-01",
            "2026-06-01",
            ["load_frcstd_7_day"],
            area=None,
            row_count=50001,
        )

    assert exc.value.code == SOURCE_QUERY_PLAN_ERROR
    assert "row_count must be between" in exc.value.message


def test_bounded_interval_query_requests_reject_feeds_outside_approved_plan():
    with pytest.raises(WorkbenchException) as exc:
        build_pjm_load_query_requests(
            ROOT / "registries",
            "2026-06-01",
            "2026-06-01",
            ["PJM_RT_HOURLY_LMP"],
            area=None,
            row_count=24,
        )

    assert exc.value.code == SOURCE_QUERY_PLAN_ERROR
    assert "Unsupported feed for PJM_DATAMINER_LOAD_BOUNDED_INTERVAL" in exc.value.message
