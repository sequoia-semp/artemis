from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.cache.hot_state import HotState
from pga_workbench.cli import artemis_main, build_artemis_parser, main
from pga_workbench.data.contracts import DataResult
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.serialization import read_json, write_json
from pga_workbench.services.power_system_ingestion import build_power_system_artifact_bundle
from pga_workbench.services.power_system_raw_fetches import build_raw_source_fetch_manifest
from pga_workbench.services.power_system_source_metadata import collect_pjm_data_miner_metadata_expectations
from pga_workbench.services.power_system_sources import POWER_SYSTEM_SOURCE_ERROR, build_power_system_source_publication_report
from pga_workbench.services.power_system_state import POWER_SYSTEM_STATE_ERROR, stage_power_system_bundle_candidate
from pga_workbench.services.source_query_plans import SourceQueryRequest
from pga_workbench.state.packs import publish_candidate_state_pack


ROOT = Path(__file__).resolve().parents[1]


def _minimal_bundle() -> dict:
    return build_power_system_artifact_bundle(
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


def _bundle_with_source_publications(*, data_environment: str, feed_ids: list[str]) -> dict:
    return build_power_system_artifact_bundle(
        {
            "pjm_load_fundamentals": {"run_id": "load"},
            "summary": "Load summary",
            "drivers": [{"name": "load"}],
        },
        bundle_id="test-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        data_environment=data_environment,
        source_publication_report=build_power_system_source_publication_report(
            ROOT / "registries",
            registry_feed_ids=feed_ids,
            operator_id="PJM",
            source_system="pjm_data_miner_api",
        ),
    )


def _source_readiness_fixture() -> dict:
    return {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "ready": True,
        "blockers": [],
        "preflight": {
            "ready": True,
            "blocker_count": 0,
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
                "status": "success",
                "product_family": "price",
                "registry_feed_id": "PJM_DA_HOURLY_LMP",
                "data_miner_feed": "da_hrl_lmps",
                "row_count": 1,
                "page_count": 1,
                "truncated_by_max_pages": False,
            }
        ],
        "fetch_source_rows": True,
        "contains_secret_values": False,
    }


def _source_readiness_for_feed(feed_id: str, *, row_count: int = 1) -> dict:
    return {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "ready": True,
        "blockers": [],
        "source_fetches": [
            {
                "status": "success",
                "product_family": "load",
                "registry_feed_id": feed_id,
                "data_miner_feed": feed_id,
                "row_count": row_count,
                "page_count": 1,
                "truncated_by_max_pages": False,
            }
        ],
        "fetch_source_rows": True,
        "contains_secret_values": False,
    }


def _metadata_verification_for_feed(feed_id: str) -> dict:
    return {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "definition_source": "fixture",
        "verified_feed_count": 1,
        "verified_feeds": [
            {
                "registry_feed_id": feed_id,
                "data_miner_feed": feed_id,
                "required_field_count": 1,
                "observed_field_count": 1,
            }
        ],
        "contains_secret_values": False,
    }


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


def _approved_load_forecast_publication_bundle(
    *,
    metadata_verification_report: dict | None = None,
    source_readiness_report: dict | None = None,
    raw_source_fetch_manifests: list[dict] | None = None,
) -> dict:
    payloads = [
        {
            "pjm_load_fundamentals": {"run_id": "load"},
            "summary": "Load forecast summary",
            "drivers": [{"name": "load forecast"}],
        }
    ]
    if raw_source_fetch_manifests is not None:
        payloads.append({"raw_source_fetch_manifests": raw_source_fetch_manifests})
    return build_power_system_artifact_bundle(
        *payloads,
        bundle_id="approved-load-forecast-bundle",
        as_of="2026-06-04T12:00:00Z",
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        data_environment="production",
        metadata_verification_report=metadata_verification_report,
        source_readiness_report=source_readiness_report,
        source_publication_report=build_power_system_source_publication_report(
            ROOT / "registries",
            registry_feed_ids=["load_frcstd_7_day"],
            operator_id="PJM",
            source_system="pjm_data_miner_api",
        ),
    )


def test_stage_power_system_bundle_candidate_builds_candidate_without_publish(tmp_path):
    result = stage_power_system_bundle_candidate(_minimal_bundle(), tmp_path, "candidate-1")

    assert result["state_id"] == "candidate-1"
    assert result["published"] is False
    assert (tmp_path / "candidates" / "candidate-1" / "state_pack.json").exists()
    assert not (tmp_path / "accepted" / "candidate-1").exists()
    assert not (tmp_path / "current.json").exists()

    payload = read_json(tmp_path / "candidates" / "candidate-1" / "state_pack.json")
    assert payload["artifacts"]["power_system_artifact_bundle"]["bundle_id"] == "test-bundle"
    assert payload["manifest"]["inputs"][0]["artifact"] == "power_system_artifact_bundle"


def test_stage_power_system_bundle_candidate_rejects_invalid_bundle(tmp_path):
    with pytest.raises(WorkbenchException) as exc:
        stage_power_system_bundle_candidate({"summary": "not a bundle"}, tmp_path, "candidate-1", as_of="2026-06-04T12:00:00Z")

    assert exc.value.code == "POWER_SYSTEM_INGESTION_ERROR"


def test_stage_power_system_bundle_candidate_requires_as_of_when_bundle_lacks_it(tmp_path):
    bundle = _minimal_bundle()
    bundle["power_system_artifact_bundle"].pop("as_of")

    with pytest.raises(WorkbenchException) as exc:
        stage_power_system_bundle_candidate(bundle, tmp_path, "candidate-1")

    assert exc.value.code == POWER_SYSTEM_STATE_ERROR
    assert "as_of is required" in exc.value.message


def test_stage_power_system_bundle_candidate_cli_writes_report(tmp_path):
    bundle_path = tmp_path / "bundle.json"
    state_root = tmp_path / "state"
    output = tmp_path / "stage_report.json"
    write_json(bundle_path, _minimal_bundle())

    assert (
        main(
            [
                "stage-power-system-bundle-candidate",
                "--bundle",
                str(bundle_path),
                "--state-root",
                str(state_root),
                "--state-id",
                "candidate-1",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    report = read_json(output)
    assert report["state_id"] == "candidate-1"
    assert report["published"] is False
    assert (state_root / "candidates" / "candidate-1" / "state_pack.json").exists()
    assert not (state_root / "current.json").exists()


def test_artemis_parser_exposes_bundle_state_candidate_staging():
    parser = build_artemis_parser()
    args = parser.parse_args(
        [
            "analyst",
            "bundle",
            "stage-state-candidate",
            "--bundle",
            "bundle.json",
            "--state-root",
            "state",
            "--state-id",
            "candidate-1",
        ]
    )

    assert args.func.__name__ == "_cmd_stage_power_system_bundle_candidate"


def test_artemis_bundle_state_candidate_can_later_publish_through_existing_guarded_path(tmp_path):
    bundle_path = tmp_path / "bundle.json"
    state_root = tmp_path / "state"
    write_json(bundle_path, _minimal_bundle())

    assert (
        artemis_main(
            [
                "analyst",
                "bundle",
                "stage-state-candidate",
                "--bundle",
                str(bundle_path),
                "--state-root",
                str(state_root),
                "--state-id",
                "candidate-1",
            ]
        )
        == 0
    )

    publish_candidate_state_pack(state_root, "candidate-1")
    assert HotState(state_root).artifacts()["power_system_artifact_bundle"]["bundle_id"] == "test-bundle"


def test_publish_blocks_candidate_source_publications_for_production_bundles(tmp_path):
    bundle = _bundle_with_source_publications(data_environment="production", feed_ids=["hrl_load_metered"])
    stage_power_system_bundle_candidate(bundle, tmp_path, "candidate-1")

    with pytest.raises(WorkbenchException) as exc:
        publish_candidate_state_pack(tmp_path, "candidate-1")

    assert exc.value.code == POWER_SYSTEM_SOURCE_ERROR
    assert "PJM_DATAMINER_LOAD_ACTUALS" in exc.value.message
    assert (tmp_path / "candidates" / "candidate-1" / "state_pack.json").exists()
    assert not (tmp_path / "accepted" / "candidate-1").exists()
    assert not (tmp_path / "current.json").exists()


def test_publish_allows_candidate_source_publication_evidence_for_local_fixture_bundles(tmp_path):
    bundle = _bundle_with_source_publications(data_environment="fixture", feed_ids=["hrl_load_metered"])
    stage_power_system_bundle_candidate(bundle, tmp_path, "candidate-1")

    publish_candidate_state_pack(tmp_path, "candidate-1")

    assert HotState(tmp_path).artifacts()["power_system_artifact_bundle"]["data_environment"] == "fixture"


def test_publish_blocks_approved_source_publications_without_readiness_evidence(tmp_path):
    bundle = _approved_load_forecast_publication_bundle()
    stage_power_system_bundle_candidate(bundle, tmp_path, "candidate-1")

    with pytest.raises(WorkbenchException) as exc:
        publish_candidate_state_pack(tmp_path, "candidate-1")

    assert exc.value.code == POWER_SYSTEM_SOURCE_ERROR
    assert "Approved source publications require publish evidence sections" in exc.value.message
    assert "source_readiness" in exc.value.message
    assert "metadata_verification" in exc.value.message
    assert "raw_source_fetches" in exc.value.message
    assert (tmp_path / "candidates" / "candidate-1" / "state_pack.json").exists()
    assert not (tmp_path / "accepted" / "candidate-1").exists()
    assert not (tmp_path / "current.json").exists()


def test_publish_blocks_approved_source_publications_without_matching_evidence(tmp_path):
    bundle = _approved_load_forecast_publication_bundle(
        metadata_verification_report=_metadata_verification_for_feed("PJM_DA_HOURLY_LMP"),
        source_readiness_report=_source_readiness_for_feed("load_frcstd_7_day"),
        raw_source_fetch_manifests=[_raw_fetch_manifest()],
    )
    stage_power_system_bundle_candidate(bundle, tmp_path, "candidate-1")

    with pytest.raises(WorkbenchException) as exc:
        publish_candidate_state_pack(tmp_path, "candidate-1")

    assert exc.value.code == POWER_SYSTEM_SOURCE_ERROR
    assert "load_frcstd_7_day:metadata_verification" in exc.value.message
    assert not (tmp_path / "accepted" / "candidate-1").exists()
    assert not (tmp_path / "current.json").exists()


def test_publish_allows_approved_source_publications_with_matching_evidence(tmp_path):
    bundle = _approved_load_forecast_publication_bundle(
        metadata_verification_report=_metadata_verification_for_feed("load_frcstd_7_day"),
        source_readiness_report=_source_readiness_for_feed("load_frcstd_7_day"),
        raw_source_fetch_manifests=[_raw_fetch_manifest()],
    )
    stage_power_system_bundle_candidate(bundle, tmp_path, "candidate-1")

    publish_candidate_state_pack(tmp_path, "candidate-1")

    artifacts = HotState(tmp_path).artifacts()
    assert artifacts["power_system_artifact_bundle"]["bundle_id"] == "approved-load-forecast-bundle"
    assert artifacts["power_system_artifact_bundle"]["source_publications"]["selected_registry_feed_ids"] == ["load_frcstd_7_day"]


def test_publish_current_pointer_is_readable_when_state_root_is_relative(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_root = Path("relative-state")
    bundle = _approved_load_forecast_publication_bundle(
        metadata_verification_report=_metadata_verification_for_feed("load_frcstd_7_day"),
        source_readiness_report=_source_readiness_for_feed("load_frcstd_7_day"),
        raw_source_fetch_manifests=[_raw_fetch_manifest()],
    )
    stage_power_system_bundle_candidate(bundle, state_root, "candidate-1")

    publish_candidate_state_pack(state_root, "candidate-1")

    pointer = read_json(state_root / "current.json")
    assert pointer["path"] == "accepted/candidate-1"
    assert HotState(state_root).artifacts()["power_system_artifact_bundle"]["bundle_id"] == "approved-load-forecast-bundle"


def test_run_pjm_morning_pipeline_cli_builds_bundle_and_stages_candidate(tmp_path):
    bundle_output = tmp_path / "bundle.json"
    pipeline_output = tmp_path / "pipeline.json"
    state_root = tmp_path / "state"

    assert (
        main(
            [
                "run-pjm-morning-pipeline",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(bundle_output),
                "--state-root",
                str(state_root),
                "--state-id",
                "candidate-1",
                "--pipeline-output",
                str(pipeline_output),
            ]
        )
        == 0
    )

    report = read_json(pipeline_output)
    assert report["bundle_output"] == str(bundle_output)
    assert report["stage"]["state_id"] == "candidate-1"
    assert report["source_readiness"] is None
    assert report["source_publications"]["publication_count"] == 4
    assert {
        item["publication_id"]: item["authoritative_use"]
        for item in report["source_publications"]["source_publication_statuses"]
    }["PJM_DATAMINER_LOAD_ACTUALS"] == "candidate_metadata_only"
    assert report["published"] is False
    assert bundle_output.exists()
    assert (state_root / "candidates" / "candidate-1" / "state_pack.json").exists()
    assert not (state_root / "current.json").exists()


def test_run_pjm_morning_pipeline_report_includes_source_readiness_summary(tmp_path):
    bundle_output = tmp_path / "bundle.json"
    pipeline_output = tmp_path / "pipeline.json"
    readiness = tmp_path / "readiness.json"
    state_root = tmp_path / "state"
    write_json(readiness, _source_readiness_fixture())

    assert (
        main(
            [
                "run-pjm-morning-pipeline",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(bundle_output),
                "--state-root",
                str(state_root),
                "--state-id",
                "candidate-1",
                "--pipeline-output",
                str(pipeline_output),
                "--source-readiness-input",
                str(readiness),
                "--require-ready-source-readiness",
            ]
        )
        == 0
    )

    report = read_json(pipeline_output)
    assert report["source_readiness"] == {
        "ready": True,
        "blocker_count": 0,
        "fetch_source_rows": True,
        "source_fetch_statuses": [{"data_miner_feed": "da_hrl_lmps", "status": "success", "row_count": 1}],
    }
    assert report["source_publications"]["publication_count"] == 4
    assert report["published"] is False
    assert not (state_root / "current.json").exists()


def test_run_pjm_morning_pipeline_report_includes_operational_event_plan_summary(tmp_path):
    bundle_output = tmp_path / "bundle.json"
    pipeline_output = tmp_path / "pipeline.json"
    state_root = tmp_path / "state"

    assert (
        main(
            [
                "run-pjm-morning-pipeline",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                str(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json"),
                "--generation-input",
                str(ROOT / "tests" / "fixtures" / "pjm_generation_mix_minimal.json"),
                "--lmp-input",
                str(ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"),
                "--output",
                str(bundle_output),
                "--state-root",
                str(state_root),
                "--state-id",
                "candidate-1",
                "--pipeline-output",
                str(pipeline_output),
                "--include-operational-event-plan",
            ]
        )
        == 0
    )

    report = read_json(pipeline_output)
    assert report["operational_event_plan"]["approved"] is False
    assert report["operational_event_plan"]["publication_count"] == 2
    assert report["operational_event_plan"]["feed_count"] == 3
    assert report["operational_event_plan"]["blocked_publication_count"] == 2
    assert report["operational_event_plan"]["blocked_feed_count"] == 3
    assert {
        item["publication_id"]: item["authoritative_use"]
        for item in report["operational_event_plan"]["publication_statuses"]
    }["PJM_DATAMINER_OUTAGES"] == "candidate_not_publishable"
    assert report["published"] is False
    assert not (state_root / "current.json").exists()


def test_run_pjm_morning_pipeline_report_includes_raw_source_fetch_summary(tmp_path, monkeypatch):
    bundle_output = tmp_path / "bundle.json"
    pipeline_output = tmp_path / "pipeline.json"
    state_root = tmp_path / "state"

    def fake_bundle_payload(args):
        return build_power_system_artifact_bundle(
            {"pjm_load_fundamentals": {"run_id": "load"}},
            {"raw_source_fetch_manifests": [_raw_fetch_manifest()]},
            bundle_id=args.run_id,
            as_of=args.as_of,
            operator_id="PJM",
            source_system="pjm_data_miner_api",
            data_environment="fixture",
        )

    monkeypatch.setattr("pga_workbench.cli._build_pjm_morning_bundle_payload", fake_bundle_payload)

    assert (
        main(
            [
                "run-pjm-morning-pipeline",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--load-input",
                "load.json",
                "--generation-input",
                "generation.json",
                "--lmp-input",
                "lmp.json",
                "--output",
                str(bundle_output),
                "--state-root",
                str(state_root),
                "--state-id",
                "candidate-1",
                "--pipeline-output",
                str(pipeline_output),
            ]
        )
        == 0
    )

    report = read_json(pipeline_output)
    assert report["raw_source_fetches"] == {
        "manifest_count": 1,
        "total_row_count": 1,
        "total_page_count": 1,
        "truncated_manifest_count": 0,
        "source_surface_counts": {"load": 1},
        "registry_feed_ids": ["load_frcstd_7_day"],
        "query_plan_ids": ["PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"],
    }
    assert report["published"] is False
    assert not (state_root / "current.json").exists()


def test_artemis_parser_exposes_pjm_morning_pipeline():
    parser = build_artemis_parser()
    args = parser.parse_args(
        [
            "analyst",
            "bundle",
            "run-pjm-morning-pipeline",
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
            "--state-root",
            "state",
            "--state-id",
            "candidate-1",
        ]
    )

    assert args.func.__name__ == "_cmd_run_pjm_morning_pipeline"


def test_run_pjm_load_pipeline_fetches_stages_publishes_and_reads_hot_state(tmp_path, monkeypatch):
    fixture = read_json(ROOT / "tests" / "fixtures" / "pjm_load_fundamentals_minimal.json")
    expectations = collect_pjm_data_miner_metadata_expectations(ROOT / "registries")

    class FakeLoadPipelineConnector:
        account_class = "non_member"

        def __init__(self, *_args, **_kwargs):
            pass

        def available(self):
            return True

        def _connection_limit(self):
            return 1

        def fetch_definition(self, feed):
            return {"items": [{"name": field} for field in expectations[feed].required_fields]}

        def fetch(self, request):
            records = [dict(item) for item in fixture["feeds"][request.contract]]
            return DataResult(
                source="PJM Data Miner",
                contract=request.contract,
                data_environment="production",
                records=records,
                lineage={
                    "page_count": 1,
                    "max_pages": 1,
                    "truncated_by_max_pages": False,
                    "total_rows": len(records),
                    "account_class": self.account_class,
                },
            )

    bundle_output = tmp_path / "load_bundle.json"
    pipeline_output = tmp_path / "load_pipeline.json"
    state_root = tmp_path / "state"
    monkeypatch.setattr("pga_workbench.cli.load_artemis_config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr("pga_workbench.cli.PjmDataMinerConnector", FakeLoadPipelineConnector)

    assert (
        main(
            [
                "run-pjm-load-pipeline",
                "--live",
                "--as-of",
                "2026-06-04T12:00:00Z",
                "--start",
                "2026-06-04",
                "--end",
                "2026-06-04",
                "--row-count",
                "2",
                "--max-pages",
                "1",
                "--no-paginate",
                "--output",
                str(bundle_output),
                "--state-root",
                str(state_root),
                "--state-id",
                "pjm-load-live-1",
                "--pipeline-output",
                str(pipeline_output),
                "--publish",
            ]
        )
        == 0
    )

    report = read_json(pipeline_output)
    assert report["feed_ids"] == ["load_frcstd_7_day"]
    assert report["published"] is True
    assert report["source_readiness"]["ready"] is True
    assert report["source_publications"]["publication_count"] == 1
    assert report["raw_source_fetches"]["registry_feed_ids"] == ["load_frcstd_7_day"]
    assert (state_root / "current.json").exists()

    bundle = read_json(bundle_output)
    metadata = bundle["power_system_artifact_bundle"]
    assert metadata["source_publications"]["selected_registry_feed_ids"] == ["load_frcstd_7_day"]
    assert metadata["source_readiness"]["source_fetches"][0]["status"] == "success"

    hot = HotState(state_root)
    forecast_rows = hot.fundamental_best_series_records(
        metric_id="PJM.LOAD.FORECAST.SEVEN_DAY.LATEST.HOURLY_MW",
        location_id="PJM_RTO",
    )
    assert len(forecast_rows) == 2
    assert hot.fundamental_source_records(product_id="PJM.LOAD.FORECAST.SEVEN_DAY.LATEST.HOURLY_MW")


def test_artemis_parser_exposes_pjm_load_pipeline():
    parser = build_artemis_parser()
    args = parser.parse_args(
        [
            "analyst",
            "bundle",
            "run-pjm-load-pipeline",
            "--live",
            "--as-of",
            "2026-06-04T12:00:00Z",
            "--start",
            "2026-06-04",
            "--end",
            "2026-06-04",
            "--output",
            "bundle.json",
            "--state-root",
            "state",
            "--state-id",
            "candidate-1",
        ]
    )

    assert args.func.__name__ == "_cmd_run_pjm_load_pipeline"
