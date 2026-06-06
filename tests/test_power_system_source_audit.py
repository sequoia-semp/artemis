from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.cli import artemis_main, build_artemis_parser, main
from pga_workbench.data.contracts import DataResult
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.models import RunManifest
from pga_workbench.serialization import read_json, write_json
from pga_workbench.services.power_system_audit import (
    POWER_SYSTEM_AUDIT_ERROR,
    build_power_system_source_audit,
    validate_power_system_source_audit,
)
from pga_workbench.services.power_system_ingestion import build_power_system_artifact_bundle
from pga_workbench.services.power_system_operational_events import build_operational_event_candidate_plan
from pga_workbench.services.power_system_raw_fetches import build_raw_source_fetch_manifest
from pga_workbench.services.power_system_sources import build_power_system_source_publication_report
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
        query={"rowCount": 1, "startRow": 1, "fields": "datetime_beginning_utc,load_mw"},
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
            records=[{"load_mw": 95000}],
            lineage={"page_count": 1, "max_pages": 1, "truncated_by_max_pages": False},
        ),
        query_execution_summary={"plan_id": "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"},
    )


def _source_audit_bundle() -> dict:
    return build_power_system_artifact_bundle(
        {"pjm_load_fundamentals": {"run_id": "load"}},
        {"raw_source_fetch_manifests": [_raw_fetch_manifest()]},
        bundle_id="audit-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        data_environment="fixture",
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
        source_publication_report=build_power_system_source_publication_report(
            ROOT / "registries",
            registry_feed_ids=["hrl_load_metered", "load_frcstd_7_day"],
            operator_id="PJM",
            source_system="pjm_data_miner_api",
        ),
        operational_event_plan=build_operational_event_candidate_plan(ROOT / "registries"),
    )


def test_power_system_source_audit_summarizes_bundle_evidence_without_rows():
    audit = build_power_system_source_audit(_source_audit_bundle())

    validate_power_system_source_audit(audit, ROOT / "schemas")
    assert audit["ready"] is False
    assert set(audit["blockers"]) == {
        "source_readiness_not_ready",
        "candidate_source_publications_present",
        "operational_events_not_approved",
    }
    assert audit["summary"] == {
        "source_fetch_rows": 0,
        "raw_fetch_manifest_count": 1,
        "candidate_publication_count": 1,
        "blocked_operational_event_publication_count": 2,
        "blocked_operational_event_feed_count": 3,
    }
    assert audit["raw_source_fetches"]["total_row_count"] == 1
    assert audit["contains_raw_records"] is False
    assert audit["contains_secret_values"] is False
    assert "load_mw" not in str(audit)
    assert "95000" not in str(audit)
    assert "source unavailable" not in str(audit)


def test_power_system_source_audit_schema_rejects_unredacted_report():
    audit = build_power_system_source_audit(_source_audit_bundle())
    audit["contains_secret_values"] = True

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_source_audit(audit, ROOT / "schemas")

    assert exc.value.code == POWER_SYSTEM_AUDIT_ERROR
    assert "contains_secret_values" in exc.value.message


def test_power_system_source_audit_rejects_disallowed_secret_field_in_redacted_evidence(monkeypatch):
    bundle = _source_audit_bundle()
    bundle["power_system_artifact_bundle"]["preflight"]["api_key"] = "must-not-be-trusted-by-flag"

    monkeypatch.setattr("pga_workbench.services.power_system_audit.validate_power_system_artifact_bundle", lambda _: None)

    with pytest.raises(WorkbenchException) as exc:
        build_power_system_source_audit(bundle)

    assert exc.value.code == POWER_SYSTEM_AUDIT_ERROR
    assert "disallowed secret field" in exc.value.message
    assert "api_key" in exc.value.message


def test_power_system_source_audit_cli_reads_bundle_file(tmp_path):
    bundle_path = tmp_path / "bundle.json"
    output = tmp_path / "audit.json"
    write_json(bundle_path, _source_audit_bundle())

    assert main(["power-system-source-audit", "--bundle", str(bundle_path), "--output", str(output), "--allow-blockers"]) == 0

    audit = read_json(output)
    assert audit["bundle_id"] == "audit-bundle"
    assert audit["ready"] is False
    assert audit["summary"]["raw_fetch_manifest_count"] == 1


def test_artemis_source_audit_cli_reads_hotstate(tmp_path):
    manifest = RunManifest(run_id="state-1", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "state-1", "2026-06-04T12:00:00Z", _source_audit_bundle(), manifest)
    publish_candidate_state_pack(tmp_path, "state-1")
    output = tmp_path / "audit.json"

    assert artemis_main(["analyst", "bundle", "source-audit", "--state-root", str(tmp_path), "--output", str(output), "--allow-blockers"]) == 0

    audit = read_json(output)
    assert audit["operator_id"] == "PJM"
    assert audit["summary"]["candidate_publication_count"] == 1
    assert audit["summary"]["blocked_operational_event_feed_count"] == 3


def test_artemis_parser_exposes_source_audit_command():
    parser = build_artemis_parser()
    args = parser.parse_args(["analyst", "bundle", "source-audit", "--bundle", "bundle.json"])

    assert args.func.__name__ == "_cmd_power_system_source_audit"
