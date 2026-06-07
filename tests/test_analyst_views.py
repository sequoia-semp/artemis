from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.analyst.view_engine import VIEW_ERROR, build_view
from pga_workbench.cli import artemis_main
from pga_workbench.data.contracts import DataResult
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.models import RunManifest
from pga_workbench.serialization import read_json
from pga_workbench.services.power_system_raw_fetches import build_raw_source_fetch_manifest
from pga_workbench.services.power_system_ingestion import build_power_system_artifact_bundle
from pga_workbench.services.power_system_operational_events import build_operational_event_candidate_plan
from pga_workbench.services.source_query_plans import SourceQueryRequest
from pga_workbench.state.packs import build_candidate_state_pack, publish_candidate_state_pack


ROOT = Path(__file__).resolve().parents[1]


def _raw_fetch_manifest() -> dict:
    request = SourceQueryRequest(
        request_id="PJM_DATAMINER_LOAD_BOUNDED_INTERVAL.load_frcstd_7_day.2026-06-01.2026-06-01",
        request_kind="source_rows",
        registry_feed_id="load_frcstd_7_day",
        data_miner_feed="load_frcstd_7_day",
        pnode_id=None,
        window_start="2026-06-01",
        window_end="2026-06-01",
        query={"rowCount": 24, "startRow": 1, "fields": "datetime_beginning_utc,load_mw"},
        paginate=False,
        max_pages=1,
        query_plan={"plan_id": "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"},
    )
    return build_raw_source_fetch_manifest(
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        source_surface="load",
        request_record=request,
        result=DataResult(
            source="PJM Data Miner",
            contract="load_frcstd_7_day",
            data_environment="fixture",
            records=[{"load_mw": value} for value in range(24)],
            lineage={"page_count": 1, "max_pages": 1, "truncated_by_max_pages": False},
        ),
        query_execution_summary={"plan_id": "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"},
    )


def test_current_day_view_builds_schema_valid_payload():
    view = build_view(ROOT, "current-day", read_json(ROOT / "tests/fixtures/views/current_day_minimal.json"))

    assert view["view_type"] == "current_day"
    assert view["horizon"]["start_date"] == "2026-06-04"
    assert view["missing_inputs"] == []
    assert view["data_quality"]["fixture_mode"] is False


def test_prior_day_and_fourteen_day_views_build():
    prior = build_view(ROOT, "prior-day-retrospective", read_json(ROOT / "tests/fixtures/views/prior_day_minimal.json"))
    fourteen = build_view(ROOT, "fourteen-day-fundamentals", read_json(ROOT / "tests/fixtures/views/fourteen_day_minimal.json"))
    delta = build_view(ROOT, "forecast-actual-delta", read_json(ROOT / "tests/fixtures/views/forecast_actual_delta_minimal.json"))

    assert prior["view_type"] == "prior_day_retrospective"
    assert prior["horizon"]["type"] == "prior_day"
    assert fourteen["horizon"]["start_date"] == "2026-05-21"
    assert fourteen["horizon"]["end_date"] == "2026-06-18"
    assert delta["view_type"] == "forecast_actual_delta"


def test_view_build_rejects_fixture_data_without_explicit_flag():
    with pytest.raises(WorkbenchException):
        build_view(ROOT, "current-day", read_json(ROOT / "tests/fixtures/views/fixture_data_minimal.json"))


def test_view_build_allows_fixture_data_when_explicit():
    view = build_view(ROOT, "current-day", read_json(ROOT / "tests/fixtures/views/fixture_data_minimal.json"), allow_fixture=True)

    assert view["data_quality"]["fixture_mode"] is True


def test_view_build_allows_grounded_quantitative_summary_claim():
    payload = read_json(ROOT / "tests/fixtures/views/current_day_minimal.json")
    payload["summary"] = "Actual load is 1,000 MW."
    payload["inputs"] = {
        "actual_load": [
            {
                "delivery_start": "2026-06-04T13:00:00Z",
                "delivery_end": "2026-06-04T14:00:00Z",
                "value": 1000,
            }
        ]
    }

    view = build_view(ROOT, "current-day", payload)

    assert view["summary"] == "Actual load is 1,000 MW."


def test_view_build_rejects_unsupported_quantitative_summary_claim():
    payload = read_json(ROOT / "tests/fixtures/views/current_day_minimal.json")
    payload["summary"] = "Actual load is 999 MW."
    payload["inputs"] = {
        "actual_load": [
            {
                "delivery_start": "2026-06-04T13:00:00Z",
                "delivery_end": "2026-06-04T14:00:00Z",
                "value": 1000,
            }
        ]
    }

    with pytest.raises(WorkbenchException) as exc:
        build_view(ROOT, "current-day", payload)

    assert exc.value.code == VIEW_ERROR
    assert "Unsupported quantitative claim" in exc.value.message
    assert "summary=999" in exc.value.message


def test_artemis_view_build_can_merge_hot_state_artifacts(tmp_path):
    manifest = RunManifest(run_id="state-1", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    artifacts = {
        "summary": "Hot state summary",
        "drivers": [{"name": "load", "direction": "up"}],
        "source_lineage": [{"source": "accepted_state_fixture"}],
        "inputs": {
            "actual_load": [
                {
                    "delivery_start": "2026-06-04T13:00:00Z",
                    "delivery_end": "2026-06-04T14:00:00Z",
                    "value": 1000,
                }
            ]
        },
    }
    build_candidate_state_pack(tmp_path, "state-1", "2026-06-04T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "state-1")

    input_path = tmp_path / "input.json"
    output_path = tmp_path / "view.json"
    input_path.write_text('{"as_of": "2026-06-04", "data_environment": "development"}\n', encoding="utf-8")

    assert artemis_main(["analyst", "view", "build", "--template", "current-day", "--input", str(input_path), "--output", str(output_path), "--state-root", str(tmp_path)]) == 0
    view = read_json(output_path)

    assert view["summary"] == "Hot state summary"
    assert view["drivers"][0]["name"] == "load"
    assert view["source_lineage"][-1]["source"] == "hot_state"


def test_artemis_view_build_can_read_hot_state_without_input_file(tmp_path):
    manifest = RunManifest(run_id="state-2", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    artifacts = {
        "summary": "Accepted state only summary",
        "drivers": [{"name": "generation", "direction": "flat"}],
        "inputs": {
            "actual_load": [
                {
                    "delivery_start": "2026-06-04T13:00:00Z",
                    "delivery_end": "2026-06-04T14:00:00Z",
                    "value": 1100,
                }
            ]
        },
    }
    build_candidate_state_pack(tmp_path, "state-2", "2026-06-04T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "state-2")
    output_path = tmp_path / "view.json"

    assert artemis_main(
        [
            "analyst",
            "view",
            "build",
            "--template",
            "current-day",
            "--output",
            str(output_path),
            "--state-root",
            str(tmp_path),
        ]
    ) == 0

    view = read_json(output_path)
    assert view["summary"] == "Accepted state only summary"
    assert view["horizon"]["start_date"] == "2026-06-04"
    assert view["drivers"][0]["name"] == "generation"


def test_artemis_view_build_projects_bundle_source_evidence_from_hot_state(tmp_path):
    manifest = RunManifest(run_id="state-3", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    bundle = build_power_system_artifact_bundle(
        {
            "pjm_load_fundamentals": {"run_id": "load"},
            "summary": "Load summary",
        },
        {"raw_source_fetch_manifests": [_raw_fetch_manifest()]},
        bundle_id="bundle-1",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        data_environment="development",
        preflight_report={
            "operator_id": "PJM",
            "source_system": "pjm_data_miner_api",
            "ready": True,
            "blockers": [],
            "selected_feeds": {"load": ["load_frcstd_7_day"]},
            "credential_checks": {"ARTEMIS_PJM_API_KEY": {"configured": True, "value_redacted": True}},
        },
        metadata_verification_report={
            "operator_id": "PJM",
            "source_system": "pjm_data_miner_api",
            "definition_source": "fixture",
            "verified_feed_count": 1,
            "verified_feeds": [],
        },
        source_readiness_report={
            "operator_id": "PJM",
            "source_system": "pjm_data_miner_api",
            "ready": False,
            "blockers": ["source unavailable"],
            "fetch_source_rows": True,
            "source_fetches": [
                {
                    "status": "error",
                    "product_family": "load",
                    "registry_feed_id": "load_frcstd_7_day",
                    "data_miner_feed": "load_frcstd_7_day",
                    "row_count": 0,
                    "page_count": 0,
                    "truncated_by_max_pages": False,
                    "error_code": "SOURCE_DOWN",
                }
            ],
            "contains_secret_values": False,
        },
        operational_event_plan=build_operational_event_candidate_plan(ROOT / "registries"),
    )
    build_candidate_state_pack(tmp_path, "state-3", "2026-06-04T12:00:00Z", bundle, manifest)
    publish_candidate_state_pack(tmp_path, "state-3")
    output_path = tmp_path / "view.json"

    assert artemis_main(
        [
            "analyst",
            "view",
            "build",
            "--template",
            "current-day",
            "--output",
            str(output_path),
            "--state-root",
            str(tmp_path),
        ]
    ) == 0

    view = read_json(output_path)
    by_type = {item["evidence_type"]: item for item in view["evidence"]}
    assert by_type["source_preflight"]["ready"] is True
    assert by_type["source_metadata_verification"]["verified_feed_count"] == 1
    assert by_type["source_readiness"]["ready"] is False
    assert by_type["source_readiness"]["source_fetch_count"] == 1
    assert by_type["raw_source_fetches"]["total_row_count"] == 24
    assert by_type["operational_event_plan"]["blocked_feed_count"] == 3
    assert all(item["contains_secret_values"] is False for item in view["evidence"])
    assert "SOURCE_DOWN" not in str(view["evidence"])


def test_artemis_view_build_requires_input_or_hot_state(tmp_path):
    with pytest.raises(WorkbenchException) as exc:
        artemis_main(["analyst", "view", "build", "--template", "current-day", "--output", str(tmp_path / "view.json")])

    assert exc.value.code == "ANALYST_VIEW_INPUT_REQUIRED"
