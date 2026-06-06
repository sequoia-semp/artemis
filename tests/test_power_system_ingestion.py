from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.cli import artemis_main, build_artemis_parser, main
from pga_workbench.data.contracts import DataResult
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.serialization import read_json, write_json
from pga_workbench.services.power_system_ingestion import (
    POWER_SYSTEM_INGESTION_ERROR,
    build_power_system_artifact_bundle,
    validate_power_system_artifact_bundle,
)
from pga_workbench.services.power_system_raw_fetches import build_raw_source_fetch_manifest
from pga_workbench.services.power_system_preflight import (
    DEFAULT_PJM_LOAD_FEEDS,
    DEFAULT_PJM_PRICE_FEEDS,
    selected_pjm_data_miner_metadata_feeds,
)
from pga_workbench.services.power_system_operational_events import build_operational_event_candidate_plan
from pga_workbench.services.power_system_source_metadata import collect_pjm_data_miner_metadata_expectations
from pga_workbench.services.power_system_sources import build_power_system_source_publication_report
from pga_workbench.services.source_query_plans import SourceQueryRequest


ROOT = Path(__file__).resolve().parents[1]


def _write_metadata_fixture(path: Path, feeds: list[str]) -> None:
    expectations = collect_pjm_data_miner_metadata_expectations(ROOT / "registries")
    write_json(
        path,
        {
            "feeds": {
                feed: {"fields": [{"name": field} for field in expectations[feed].required_fields]}
                for feed in feeds
            }
        },
    )


def _bundle_metadata_feeds() -> list[str]:
    return selected_pjm_data_miner_metadata_feeds(
        ROOT / "registries",
        DEFAULT_PJM_LOAD_FEEDS,
        DEFAULT_PJM_PRICE_FEEDS,
        include_generation_mix=True,
    )


def _source_readiness_fixture(*, ready: bool = True) -> dict:
    blockers = [] if ready else ["source unavailable"]
    return {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "ready": ready,
        "blockers": blockers,
        "preflight": {
            "ready": ready,
            "blocker_count": len(blockers),
            "selected_feeds": {"load": ["load_frcstd_7_day"]},
            "credential_checks": {"ARTEMIS_PJM_API_KEY": {"configured": True, "value_redacted": True}},
            "contains_secret_values": False,
        },
        "metadata_verification": {
            "definition_source": "fixture",
            "verified_feed_count": 1,
            "verified_feeds": [
                {
                    "registry_feed_id": "PJM_DA_HOURLY_LMP",
                    "data_miner_feed": "da_hrl_lmps",
                    "required_field_count": 7,
                    "observed_field_count": 12,
                }
            ],
            "contains_secret_values": False,
        },
        "source_fetches": [
            {
                "status": "success" if ready else "error",
                "product_family": "price",
                "registry_feed_id": "PJM_DA_HOURLY_LMP",
                "data_miner_feed": "da_hrl_lmps",
                "row_count": 1 if ready else 0,
                "page_count": 1 if ready else 0,
                "truncated_by_max_pages": False,
                **({} if ready else {"error_code": "SOURCE_DOWN", "error_message": "redacted failure"}),
            }
        ],
        "fetch_source_rows": True,
        "contains_secret_values": False,
    }


def _raw_fetch_manifest(*, feed_id: str = "load_frcstd_7_day", surface: str = "load", rows: list[dict] | None = None) -> dict:
    request = SourceQueryRequest(
        request_id=f"PJM_DATAMINER_LOAD_BOUNDED_INTERVAL.{feed_id}.2026-06-01.2026-06-01",
        request_kind="source_rows",
        registry_feed_id=feed_id,
        data_miner_feed=feed_id,
        pnode_id=None,
        window_start="2026-06-01",
        window_end="2026-06-01",
        query={"rowCount": 1, "startRow": 1, "fields": "datetime_beginning_utc,load_mw"},
        paginate=False,
        max_pages=1,
        query_plan={"plan_id": "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"},
    )
    return build_raw_source_fetch_manifest(
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        source_surface=surface,
        request_record=request,
        result=DataResult(
            source="PJM Data Miner",
            contract=feed_id,
            data_environment="fixture",
            records=rows if rows is not None else [{"load_mw": 95000}],
            lineage={"page_count": 1, "max_pages": 1, "truncated_by_max_pages": False},
        ),
        query_execution_summary={"plan_id": "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"},
    )


def test_power_system_artifact_bundle_wraps_composition_metadata():
    bundle = build_power_system_artifact_bundle(
        {
            "pjm_load_fundamentals": {"run_id": "load"},
            "summary": "Load summary",
            "drivers": [{"name": "load"}],
        },
        {
            "pjm_generation_mix": {"run_id": "generation"},
            "summary": "Generation summary",
            "drivers": [{"name": "generation"}],
        },
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        data_environment="fixture",
    )

    validate_power_system_artifact_bundle(bundle)
    assert bundle["power_system_artifact_bundle"]["bundle_id"] == "test-bundle"
    assert bundle["power_system_artifact_bundle"]["payload_count"] == 2
    assert bundle["power_system_artifact_bundle"]["composition_product_keys"] == [
        "pjm_generation_mix",
        "pjm_load_fundamentals",
    ]
    assert "Load summary" in bundle["summary"]
    assert "Generation summary" in bundle["summary"]


def test_power_system_artifact_bundle_embeds_redacted_preflight_evidence():
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        preflight_report={
            "operator_id": "PJM",
            "source_system": "pjm_data_miner_api",
            "ready": True,
            "blockers": [],
            "selected_feeds": {"load": ["load_frcstd_7_day"]},
            "query_plan": {"planned_request_count": 1},
            "query_plans": {
                "load": {
                    "plan_id": "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL",
                    "planned_request_count": 1,
                    "built_request_count": 1,
                    "account_class": "non_member",
                    "lineage": {"feed_ids": ["load_frcstd_7_day"]},
                    "raw_debug_value": "not embedded",
                },
                "price": {
                    "plan_id": "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS",
                    "planned_request_count": 1,
                    "max_connections_per_minute": 6,
                    "windows": [{"start": "2026-06-04", "end": "2026-06-04"}],
                },
            },
            "credential_checks": {"ARTEMIS_PJM_API_KEY": {"configured": True, "value_redacted": True}},
        },
    )

    preflight = bundle["power_system_artifact_bundle"]["preflight"]
    assert preflight["ready"] is True
    assert preflight["query_plan"] == {"planned_request_count": 1}
    assert preflight["query_plans"]["load"] == {
        "plan_id": "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL",
        "planned_request_count": 1,
        "built_request_count": 1,
        "account_class": "non_member",
        "lineage": {"feed_ids": ["load_frcstd_7_day"]},
    }
    assert preflight["query_plans"]["price"]["windows"] == [{"start": "2026-06-04", "end": "2026-06-04"}]
    assert "raw_debug_value" not in preflight["query_plans"]["load"]
    assert preflight["credential_checks"]["ARTEMIS_PJM_API_KEY"]["configured"] is True
    assert preflight["credential_checks"]["ARTEMIS_PJM_API_KEY"]["value_redacted"] is True
    assert preflight["contains_secret_values"] is False


def test_power_system_artifact_bundle_embeds_redacted_metadata_verification_evidence():
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        metadata_verification_report={
            "operator_id": "PJM",
            "source_system": "pjm_data_miner_api",
            "definition_source": "fixture",
            "verified_feed_count": 1,
            "include_candidate": True,
            "verified_feeds": [
                {
                    "registry_feed_id": "PJM_RT_HOURLY_LMP",
                    "data_miner_feed": "rt_hrl_lmps",
                    "required_field_count": 7,
                    "observed_field_count": 12,
                    "missing_fields": [],
                    "raw_definition": {"fields": ["not embedded"]},
                }
            ],
        },
    )

    evidence = bundle["power_system_artifact_bundle"]["metadata_verification"]
    assert evidence["definition_source"] == "fixture"
    assert evidence["verified_feed_count"] == 1
    assert evidence["contains_secret_values"] is False
    assert evidence["verified_feeds"] == [
        {
            "registry_feed_id": "PJM_RT_HOURLY_LMP",
            "data_miner_feed": "rt_hrl_lmps",
            "required_field_count": 7,
            "observed_field_count": 12,
        }
    ]


def test_power_system_artifact_bundle_embeds_redacted_source_readiness_evidence():
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        source_readiness_report=_source_readiness_fixture(),
    )

    evidence = bundle["power_system_artifact_bundle"]["source_readiness"]
    assert evidence["ready"] is True
    assert evidence["blocker_count"] == 0
    assert evidence["source_fetches"] == [
        {
            "status": "success",
            "product_family": "price",
            "registry_feed_id": "PJM_DA_HOURLY_LMP",
            "data_miner_feed": "da_hrl_lmps",
            "row_count": 1,
            "page_count": 1,
            "truncated_by_max_pages": False,
        }
    ]
    assert evidence["contains_secret_values"] is False


def test_power_system_artifact_bundle_embeds_redacted_query_execution_evidence():
    readiness = _source_readiness_fixture()
    readiness["query_execution"] = {
        "plan_id": "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS",
        "planned_request_count": 2,
        "built_request_count": 2,
        "account_class": "member",
        "max_connections_per_minute": 600,
        "request_kinds": {"metadata": 1, "source_rows": 1},
        "registry_feed_ids": ["PJM_PNODE", "PJM_DA_HOURLY_LMP"],
        "pnode_ids": [51288],
        "date_windows": [{"start": "2026-06-01", "end": "2026-06-01"}],
        "contains_secret_values": False,
    }
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        source_readiness_report=readiness,
    )

    evidence = bundle["power_system_artifact_bundle"]["source_readiness"]["query_execution"]
    assert evidence["plan_id"] == "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS"
    assert evidence["built_request_count"] == 2
    assert evidence["contains_secret_values"] is False


def test_power_system_artifact_bundle_embeds_source_publication_lifecycle_evidence():
    publication_report = build_power_system_source_publication_report(
        ROOT / "registries",
        registry_feed_ids=["load_frcstd_7_day", "load_frcstd_hist", "PJM_DA_HOURLY_LMP", "PJM_GEN_BY_FUEL"],
        operator_id="PJM",
        source_system="pjm_data_miner_api",
    )
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        source_publication_report=publication_report,
    )

    evidence = bundle["power_system_artifact_bundle"]["source_publications"]
    assert evidence["contains_secret_values"] is False
    assert evidence["publication_count"] == 3
    by_id = {item["publication_id"]: item for item in evidence["source_publications"]}
    assert by_id["PJM_DATAMINER_LOAD_FORECASTS"]["publication_lifecycle"]["revision_policy"] == "latest_and_revision_history_separate"
    assert by_id["PJM_DATAMINER_HOURLY_LMP_CORE"]["publication_lifecycle"]["authoritative_use"] == "approved_source_surface"
    assert by_id["PJM_DATAMINER_GENERATION_BY_FUEL"]["publication_lifecycle"]["cadence"] == "hourly"


def test_power_system_artifact_bundle_embeds_raw_source_fetch_manifest_evidence():
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        {"raw_source_fetch_manifests": [_raw_fetch_manifest()]},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
    )

    evidence = bundle["power_system_artifact_bundle"]["raw_source_fetches"]
    assert evidence["contains_raw_records"] is False
    assert evidence["contains_secret_values"] is False
    assert evidence["manifest_count"] == 1
    assert evidence["total_row_count"] == 1
    assert evidence["total_page_count"] == 1
    assert evidence["source_surface_counts"] == {"load": 1}
    assert evidence["registry_feed_ids"] == ["load_frcstd_7_day"]
    assert evidence["query_plan_ids"] == ["PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"]
    assert evidence["manifests"][0]["raw_records_sha256"]
    assert "load_mw" not in str(evidence)
    assert "95000" not in str(evidence)


def test_power_system_artifact_bundle_embeds_operational_event_candidate_plan_evidence():
    plan = build_operational_event_candidate_plan(ROOT / "registries")
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        operational_event_plan=plan,
    )

    evidence = bundle["power_system_artifact_bundle"]["operational_event_plan"]
    assert evidence["contains_secret_values"] is False
    assert evidence["approved"] is False
    assert evidence["publication_count"] == 2
    assert evidence["feed_count"] == 3
    assert evidence["blocked_publication_count"] == 2
    assert evidence["blocked_feed_count"] == 3
    by_id = {item["publication_id"]: item for item in evidence["publications"]}
    assert by_id["PJM_DATAMINER_OUTAGES"]["authoritative_use"] == "candidate_not_publishable"
    assert by_id["PJM_DATAMINER_OUTAGES"]["feeds"][0]["topology_linkage"] == "not_approved"


def test_power_system_artifact_bundle_rejects_stale_metadata():
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
    )
    bundle["power_system_artifact_bundle"]["payload_count"] = 999

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_bundle(bundle)

    assert exc.value.code == POWER_SYSTEM_INGESTION_ERROR
    assert "payload count" in exc.value.message


def test_power_system_artifact_bundle_rejects_unredacted_preflight_claim():
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
    )
    bundle["power_system_artifact_bundle"]["preflight"] = {"contains_secret_values": True}

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_bundle(bundle)

    assert exc.value.code == POWER_SYSTEM_INGESTION_ERROR
    assert "redacted" in exc.value.message


def test_power_system_artifact_bundle_rejects_unredacted_preflight_query_plan_claim():
    with pytest.raises(WorkbenchException) as exc:
        build_power_system_artifact_bundle(
            {"pjm_load_fundamentals": {"run_id": "load"}},
            bundle_id="test-bundle",
            as_of="2026-06-04T12:00:00Z",
            operator_id="PJM",
            source_system="pjm_data_miner_api",
            preflight_report={
                "operator_id": "PJM",
                "source_system": "pjm_data_miner_api",
                "ready": True,
                "blockers": [],
                "query_plans": {
                    "load": {
                        "plan_id": "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL",
                        "contains_secret_values": True,
                    }
                },
                "credential_checks": {"ARTEMIS_PJM_API_KEY": {"configured": True}},
            },
        )

    assert exc.value.code == POWER_SYSTEM_INGESTION_ERROR
    assert "query_plans.load evidence must be redacted" in exc.value.message


def test_power_system_artifact_bundle_rejects_unredacted_metadata_verification_claim():
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
    )
    bundle["power_system_artifact_bundle"]["metadata_verification"] = {"contains_secret_values": True}

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_bundle(bundle)

    assert exc.value.code == POWER_SYSTEM_INGESTION_ERROR
    assert "redacted" in exc.value.message


def test_power_system_artifact_bundle_rejects_unredacted_source_readiness_claim():
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
    )
    bundle["power_system_artifact_bundle"]["source_readiness"] = {"contains_secret_values": True}

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_bundle(bundle)

    assert exc.value.code == POWER_SYSTEM_INGESTION_ERROR
    assert "redacted" in exc.value.message


def test_power_system_artifact_bundle_rejects_unredacted_query_execution_claim():
    readiness = _source_readiness_fixture()
    readiness["query_execution"] = {
        "plan_id": "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS",
        "planned_request_count": 1,
        "built_request_count": 1,
        "account_class": "member",
        "max_connections_per_minute": 600,
        "request_kinds": {},
        "registry_feed_ids": [],
        "pnode_ids": [],
        "date_windows": [],
        "contains_secret_values": True,
    }

    with pytest.raises(WorkbenchException) as exc:
        build_power_system_artifact_bundle(
            {"pjm_load_fundamentals": {"run_id": "load"}},
            bundle_id="test-bundle",
            as_of="2026-06-04T12:00:00Z",
            operator_id="PJM",
            source_system="pjm_data_miner_api",
            source_readiness_report=readiness,
        )

    assert exc.value.code == POWER_SYSTEM_INGESTION_ERROR
    assert "query_execution must be redacted" in exc.value.message


def test_power_system_artifact_bundle_rejects_unredacted_source_publication_claim():
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
    )
    bundle["power_system_artifact_bundle"]["source_publications"] = {"contains_secret_values": True}

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_bundle(bundle)

    assert exc.value.code == POWER_SYSTEM_INGESTION_ERROR
    assert "redacted" in exc.value.message


def test_power_system_artifact_bundle_rejects_unredacted_raw_fetch_manifest_input():
    manifest = _raw_fetch_manifest()
    manifest["contains_raw_records"] = True

    with pytest.raises(WorkbenchException) as exc:
        build_power_system_artifact_bundle(
            {"pjm_load_fundamentals": {"run_id": "load"}},
            {"raw_source_fetch_manifests": [manifest]},
            bundle_id="test-bundle",
            as_of="2026-06-04T12:00:00Z",
            operator_id="PJM",
            source_system="pjm_data_miner_api",
        )

    assert exc.value.code == POWER_SYSTEM_INGESTION_ERROR
    assert "redacted" in exc.value.message


def test_power_system_artifact_bundle_rejects_unredacted_raw_fetch_evidence_claim():
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        {"raw_source_fetch_manifests": [_raw_fetch_manifest()]},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
    )
    bundle["power_system_artifact_bundle"]["raw_source_fetches"]["contains_secret_values"] = True

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_bundle(bundle)

    assert exc.value.code == POWER_SYSTEM_INGESTION_ERROR
    assert "redacted" in exc.value.message


def test_power_system_artifact_bundle_rejects_unredacted_operational_event_plan_claim():
    bundle = build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
    )
    bundle["power_system_artifact_bundle"]["operational_event_plan"] = {"contains_secret_values": True}

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_bundle(bundle)

    assert exc.value.code == POWER_SYSTEM_INGESTION_ERROR
    assert "redacted" in exc.value.message


def test_power_system_artifact_bundle_rejects_unredacted_operational_event_plan_input():
    plan = build_operational_event_candidate_plan(ROOT / "registries")
    plan["contains_secret_values"] = True

    with pytest.raises(WorkbenchException) as exc:
        build_power_system_artifact_bundle(
            {"pjm_load_fundamentals": {"run_id": "load"}},
            bundle_id="test-bundle",
            as_of="2026-06-04T12:00:00Z",
            operator_id="PJM",
            source_system="pjm_data_miner_api",
            operational_event_plan=plan,
        )

    assert exc.value.code == POWER_SYSTEM_INGESTION_ERROR
    assert "redacted" in exc.value.message


def test_build_pjm_morning_bundle_cli_writes_composed_fixture_bundle(tmp_path):
    output = tmp_path / "pjm_morning_bundle.json"
    preflight = tmp_path / "preflight.json"
    write_json(
        preflight,
        {
            "operator_id": "PJM",
            "source_system": "pjm_data_miner_api",
            "ready": True,
            "blockers": [],
            "selected_feeds": {"load": ["load_frcstd_7_day"]},
            "query_plan": {"planned_request_count": 1},
            "credential_checks": {"ARTEMIS_PJM_API_KEY": {"configured": True, "value_redacted": True}},
        },
    )

    assert (
        main(
            [
                "build-pjm-morning-bundle",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(output),
                "--preflight-input",
                str(preflight),
                "--require-ready-preflight",
                "--data-environment",
                "fixture",
            ]
        )
        == 0
    )

    payload = read_json(output)
    assert payload["power_system_artifact_bundle"]["operator_id"] == "PJM"
    assert payload["power_system_artifact_bundle"]["data_environment"] == "fixture"
    assert payload["power_system_artifact_bundle"]["preflight"]["ready"] is True
    source_publications = payload["power_system_artifact_bundle"]["source_publications"]
    assert source_publications["contains_secret_values"] is False
    assert {item["publication_id"] for item in source_publications["source_publications"]} == {
        "PJM_DATAMINER_GENERATION_BY_FUEL",
        "PJM_DATAMINER_HOURLY_LMP_CORE",
        "PJM_DATAMINER_LOAD_ACTUALS",
        "PJM_DATAMINER_LOAD_FORECASTS",
    }
    assert any(
        item["publication_id"] == "PJM_DATAMINER_LOAD_ACTUALS"
        and item["publication_lifecycle"]["authoritative_use"] == "candidate_metadata_only"
        for item in source_publications["source_publications"]
    )
    assert payload["pjm_load_fundamentals"]["run_id"] == "pjm-morning-bundle-load"
    assert payload["pjm_generation_mix"]["run_id"] == "pjm-morning-bundle-generation"
    assert payload["pjm_power_prices"]["run_id"] == "pjm-morning-bundle-prices"
    assert payload["power_price_shape_rollups"]["run_id"] == "pjm-morning-bundle-shapes"
    assert payload["artifact_composition"]["composition_product_keys"] == [
        "pjm_generation_mix",
        "pjm_load_fundamentals",
        "pjm_power_prices",
        "power_price_shape_rollups",
    ]
    assert payload["current_day_view"]["price_shapes"]["gap_count"] >= 1


def test_build_pjm_morning_bundle_cli_embeds_operational_event_candidate_plan(tmp_path):
    output = tmp_path / "pjm_morning_bundle.json"

    assert (
        main(
            [
                "build-pjm-morning-bundle",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(output),
                "--include-operational-event-plan",
                "--data-environment",
                "fixture",
            ]
        )
        == 0
    )

    evidence = read_json(output)["power_system_artifact_bundle"]["operational_event_plan"]
    assert evidence["approved"] is False
    assert evidence["publication_count"] == 2
    assert evidence["contains_secret_values"] is False


def test_build_pjm_morning_bundle_cli_rejects_required_approved_operational_events(tmp_path):
    output = tmp_path / "pjm_morning_bundle.json"

    with pytest.raises(WorkbenchException) as exc:
        main(
            [
                "build-pjm-morning-bundle",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(output),
                "--include-operational-event-plan",
                "--require-approved-operational-events",
            ]
        )

    assert exc.value.code == "POWER_SYSTEM_OPERATIONAL_EVENTS_NOT_APPROVED"


def test_build_pjm_morning_bundle_cli_embeds_ready_source_readiness(tmp_path):
    output = tmp_path / "pjm_morning_bundle.json"
    source_readiness = tmp_path / "source_readiness.json"
    write_json(source_readiness, _source_readiness_fixture())

    assert (
        main(
            [
                "build-pjm-morning-bundle",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(output),
                "--source-readiness-input",
                str(source_readiness),
                "--require-ready-source-readiness",
                "--data-environment",
                "fixture",
            ]
        )
        == 0
    )

    evidence = read_json(output)["power_system_artifact_bundle"]["source_readiness"]
    assert evidence["ready"] is True
    assert evidence["source_fetches"][0]["status"] == "success"
    assert evidence["contains_secret_values"] is False


def test_build_pjm_morning_bundle_cli_rejects_blocked_required_source_readiness(tmp_path):
    output = tmp_path / "pjm_morning_bundle.json"
    source_readiness = tmp_path / "blocked_source_readiness.json"
    write_json(source_readiness, _source_readiness_fixture(ready=False))

    with pytest.raises(WorkbenchException) as exc:
        main(
            [
                "build-pjm-morning-bundle",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(output),
                "--source-readiness-input",
                str(source_readiness),
                "--require-ready-source-readiness",
            ]
        )

    assert exc.value.code == "POWER_SYSTEM_SOURCE_READINESS_NOT_READY"


def test_build_pjm_morning_bundle_cli_requires_source_readiness_when_requested(tmp_path):
    output = tmp_path / "pjm_morning_bundle.json"

    with pytest.raises(WorkbenchException) as exc:
        main(
            [
                "build-pjm-morning-bundle",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(output),
                "--require-ready-source-readiness",
            ]
        )

    assert exc.value.code == "POWER_SYSTEM_SOURCE_READINESS_REQUIRED"


def test_build_pjm_morning_bundle_cli_embeds_fixture_metadata_verification(tmp_path):
    output = tmp_path / "pjm_morning_bundle.json"
    metadata_input = tmp_path / "metadata_fixture.json"
    _write_metadata_fixture(metadata_input, _bundle_metadata_feeds())

    assert (
        main(
            [
                "build-pjm-morning-bundle",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(output),
                "--metadata-input",
                str(metadata_input),
                "--require-metadata-verification",
                "--data-environment",
                "fixture",
            ]
        )
        == 0
    )

    evidence = read_json(output)["power_system_artifact_bundle"]["metadata_verification"]
    assert evidence["definition_source"] == "fixture"
    assert evidence["verified_feed_count"] == len(_bundle_metadata_feeds())
    assert evidence["contains_secret_values"] is False
    assert "raw_definition" not in str(evidence)


def test_build_pjm_morning_bundle_cli_requires_metadata_when_requested(tmp_path):
    output = tmp_path / "pjm_morning_bundle.json"

    with pytest.raises(WorkbenchException) as exc:
        main(
            [
                "build-pjm-morning-bundle",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(output),
                "--require-metadata-verification",
            ]
        )

    assert exc.value.code == "PJM_METADATA_VERIFICATION_REQUIRED"


def test_build_pjm_morning_bundle_live_verifies_metadata_before_source_fetch(tmp_path, monkeypatch):
    output = tmp_path / "pjm_morning_bundle.json"

    class FakeConnector:
        account_class = "member"

        def __init__(self, base_url=None, definition_base_url=None):
            self.base_url = base_url
            self.definition_base_url = definition_base_url

        def available(self):
            return True

        def fetch_definition(self, feed):
            return {"fields": []}

    def fail_source_fetch(*args, **kwargs):
        raise AssertionError("source observations should not be fetched before metadata verification passes")

    monkeypatch.setattr("pga_workbench.cli.PjmDataMinerConnector", FakeConnector)
    monkeypatch.setattr("pga_workbench.cli._fetch_live_pjm_load", fail_source_fetch)
    monkeypatch.setattr("pga_workbench.cli._fetch_live_pjm_generation_mix", fail_source_fetch)
    monkeypatch.setattr("pga_workbench.cli._fetch_live_pjm_lmp", fail_source_fetch)

    with pytest.raises(WorkbenchException) as exc:
        main(
            [
                "build-pjm-morning-bundle",
                "--live",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--start",
                "2026-06-01",
                "--end",
                "2026-06-02",
                "--pnode-id",
                "51288",
                "--output",
                str(output),
            ]
        )

    assert exc.value.code == "POWER_SYSTEM_SOURCE_METADATA_ERROR"


def test_build_pjm_morning_bundle_cli_rejects_blocked_required_preflight(tmp_path):
    output = tmp_path / "pjm_morning_bundle.json"
    preflight = tmp_path / "blocked_preflight.json"
    write_json(
        preflight,
        {
            "operator_id": "PJM",
            "source_system": "pjm_data_miner_api",
            "ready": False,
            "blockers": ["missing key"],
            "credential_checks": {"ARTEMIS_PJM_API_KEY": {"configured": False, "value_redacted": True}},
        },
    )

    with pytest.raises(WorkbenchException) as exc:
        main(
            [
                "build-pjm-morning-bundle",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(output),
                "--preflight-input",
                str(preflight),
                "--require-ready-preflight",
            ]
        )

    assert exc.value.code == "PJM_PREFLIGHT_NOT_READY"


def test_artemis_parser_exposes_pjm_morning_bundle_command():
    parser = build_artemis_parser()
    args = parser.parse_args(
        [
            "analyst",
            "bundle",
            "build-pjm-morning",
            "--as-of",
            "2026-06-04T12:00:00Z",
            "--load-input",
            "load.json",
            "--generation-input",
            "generation.json",
            "--lmp-input",
            "lmp.json",
            "--output",
            "bundle.json",
        ]
    )

    assert args.func.__name__ == "_cmd_build_pjm_morning_bundle"


def test_artemis_pjm_morning_bundle_cli_smoke(tmp_path):
    output = tmp_path / "artemis_pjm_morning_bundle.json"

    assert (
        artemis_main(
            [
                "analyst",
                "bundle",
                "build-pjm-morning",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert read_json(output)["power_system_artifact_bundle"]["bundle_id"] == "pjm-morning-bundle"
