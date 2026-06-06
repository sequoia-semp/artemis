from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.data.contracts import DataResult
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.services.artifact_composition import compose_artifact_payloads
from pga_workbench.services.power_system_raw_fetches import (
    POWER_SYSTEM_RAW_FETCH_ERROR,
    build_raw_source_fetch_manifest,
    validate_raw_source_fetch_manifests,
)
from pga_workbench.services.source_query_plans import SourceQueryRequest


ROOT = Path(__file__).resolve().parents[1]


def _request_record() -> SourceQueryRequest:
    return SourceQueryRequest(
        request_id="PJM_DATAMINER_LOAD_BOUNDED_INTERVAL.load_frcstd_7_day.2026-06-01.2026-06-01",
        request_kind="source_rows",
        registry_feed_id="load_frcstd_7_day",
        data_miner_feed="load_frcstd_7_day",
        pnode_id=None,
        window_start="2026-06-01",
        window_end="2026-06-01",
        query={
            "rowCount": 1,
            "startRow": 1,
            "fields": "evaluated_at_datetime_utc,forecast_datetime_beginning_utc,forecast_load_mw",
            "forecast_area": "RTO_COMBINED",
        },
        paginate=False,
        max_pages=1,
        query_plan={"plan_id": "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"},
    )


def test_raw_source_fetch_manifest_records_request_result_metadata_without_rows():
    manifest = build_raw_source_fetch_manifest(
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        source_surface="load",
        request_record=_request_record(),
        result=DataResult(
            source="PJM Data Miner",
            contract="load_frcstd_7_day",
            data_environment="test",
            records=[{"forecast_load_mw": 95000, "forecast_area": "RTO_COMBINED"}],
            lineage={"total_rows": 1, "page_count": 1, "max_pages": 1, "truncated_by_max_pages": False},
        ),
        query_execution_summary={"plan_id": "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"},
    )

    validate_raw_source_fetch_manifests([manifest], ROOT / "schemas")
    assert manifest["source_surface"] == "load"
    assert manifest["row_count"] == 1
    assert manifest["query_parameter_keys"] == ["fields", "forecast_area", "rowCount", "startRow"]
    assert manifest["contains_raw_records"] is False
    assert manifest["contains_secret_values"] is False
    assert "records" not in manifest
    assert len(manifest["raw_records_sha256"]) == 64


def test_raw_source_fetch_manifest_schema_fails_closed_on_raw_rows():
    manifest = build_raw_source_fetch_manifest(
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        source_surface="load",
        request_record=_request_record(),
        result=DataResult(source="PJM Data Miner", contract="load_frcstd_7_day", data_environment="test", records=[], lineage={}),
    )
    manifest["contains_raw_records"] = True

    with pytest.raises(WorkbenchException) as exc:
        validate_raw_source_fetch_manifests([manifest], ROOT / "schemas")

    assert exc.value.code == POWER_SYSTEM_RAW_FETCH_ERROR
    assert "contains_raw_records" in exc.value.message


def test_raw_source_fetch_manifests_compose_as_evidence_lists():
    manifest = build_raw_source_fetch_manifest(
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        source_surface="load",
        request_record=_request_record(),
        result=DataResult(source="PJM Data Miner", contract="load_frcstd_7_day", data_environment="test", records=[], lineage={}),
    )
    second_request = _request_record()
    second_request = SourceQueryRequest(
        request_id="PJM_DATAMINER_LOAD_BOUNDED_INTERVAL.load_frcstd_hist.2026-06-01.2026-06-01",
        request_kind=second_request.request_kind,
        registry_feed_id="load_frcstd_hist",
        data_miner_feed="load_frcstd_hist",
        pnode_id=second_request.pnode_id,
        window_start=second_request.window_start,
        window_end=second_request.window_end,
        query=second_request.query,
        paginate=second_request.paginate,
        max_pages=second_request.max_pages,
        query_plan=second_request.query_plan,
    )
    second_manifest = build_raw_source_fetch_manifest(
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        source_surface="load",
        request_record=second_request,
        result=DataResult(source="PJM Data Miner", contract="load_frcstd_hist", data_environment="test", records=[], lineage={}),
    )

    composed = compose_artifact_payloads(
        {"raw_source_fetch_manifests": [manifest]},
        {"raw_source_fetch_manifests": [second_manifest]},
    )

    assert len(composed["raw_source_fetch_manifests"]) == 2
    assert composed["artifact_composition"]["shared_list_counts"]["raw_source_fetch_manifests"] == 2
