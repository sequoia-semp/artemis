from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.cli import artemis_main, build_artemis_parser, main
from pga_workbench.serialization import read_json, write_json
from pga_workbench.services.power_system_source_metadata import (
    POWER_SYSTEM_SOURCE_METADATA_ERROR,
    collect_pjm_data_miner_metadata_expectations,
    extract_definition_fields,
    validate_power_system_source_metadata_references,
    verify_pjm_data_miner_definition,
    verify_pjm_data_miner_definitions,
)


ROOT = Path(__file__).resolve().parents[1]


def _copy_metadata_registries(tmp_path: Path) -> Path:
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in [
        "pjm_fundamental_feeds.yaml",
        "power_generation_mix_feeds.yaml",
        "power_system_price_feeds.yaml",
        "power_system_source_catalog.yaml",
    ]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")
    return registry_dir


def test_pjm_data_miner_metadata_expectations_cover_current_core_feeds():
    expectations = collect_pjm_data_miner_metadata_expectations(ROOT / "registries")
    references = validate_power_system_source_metadata_references(ROOT / "registries")

    assert {"load_frcstd_7_day", "pnode", "da_hrl_lmps", "rt_hrl_lmps", "gen_by_fuel"} <= set(expectations)
    assert "PJM_DA_HOURLY_LMP" in references["approved_catalog_feed_ids"]
    assert "total_lmp_da" in expectations["da_hrl_lmps"].required_fields
    assert "forecast_load_mw" in expectations["load_frcstd_7_day"].required_fields
    assert "fuel_type" in expectations["gen_by_fuel"].required_fields
    assert expectations["rt_fivemin_hrl_lmps"].status == "candidate"
    assert "total_lmp_rt" in expectations["rt_fivemin_hrl_lmps"].required_fields


def test_extract_definition_fields_handles_common_metadata_shapes():
    payload = {
        "fields": [{"name": "datetime_beginning_utc"}],
        "attributes": [{"fieldName": "total_lmp_rt"}],
        "columns": [{"column_name": "pnode_id"}],
        "nested": {"attribute_name": "row_is_current"},
    }

    assert extract_definition_fields(payload) == {
        "datetime_beginning_utc",
        "total_lmp_rt",
        "pnode_id",
        "row_is_current",
    }


def test_verify_pjm_data_miner_definition_accepts_matching_fixture_metadata():
    expectation = collect_pjm_data_miner_metadata_expectations(ROOT / "registries")["rt_hrl_lmps"]
    payload = {"fields": [{"name": field} for field in expectation.required_fields]}

    result = verify_pjm_data_miner_definition("rt_hrl_lmps", payload, ROOT / "registries")

    assert result["registry_feed_id"] == "PJM_RT_HOURLY_LMP"
    assert result["missing_fields"] == []
    assert result["required_field_count"] == len(expectation.required_fields)


def test_hrl_load_prelim_metadata_requires_live_source_fields_only():
    expectation = collect_pjm_data_miner_metadata_expectations(ROOT / "registries")["hrl_load_prelim"]
    payload = {
        "columns": [
            {"fieldName": "datetime_beginning_ept"},
            {"fieldName": "datetime_beginning_utc"},
            {"fieldName": "datetime_ending_ept"},
            {"fieldName": "datetime_ending_utc"},
            {"fieldName": "load_area"},
            {"fieldName": "prelim_load_avg_hourly"},
        ]
    }

    result = verify_pjm_data_miner_definition("hrl_load_prelim", payload, ROOT / "registries")

    assert {"area", "zone"}.isdisjoint(expectation.required_fields)
    assert result["missing_fields"] == []


def test_verify_pjm_data_miner_definitions_defaults_to_approved_core_feeds():
    expectations = collect_pjm_data_miner_metadata_expectations(ROOT / "registries")
    payloads = {
        feed: {"fields": [{"name": field} for field in expectation.required_fields]}
        for feed, expectation in expectations.items()
        if expectation.status == "approved_core"
    }

    report = verify_pjm_data_miner_definitions(payloads, ROOT / "registries")

    assert report["operator_id"] == "PJM"
    assert report["source_system"] == "pjm_data_miner_api"
    assert report["verified_feed_count"] == len(payloads)
    assert "hrl_load_metered" not in {item["data_miner_feed"] for item in report["verified_feeds"]}
    assert "rt_fivemin_hrl_lmps" not in {item["data_miner_feed"] for item in report["verified_feeds"]}


def test_verify_pjm_data_miner_definition_rejects_missing_fields():
    payload = {"fields": [{"name": "datetime_beginning_utc"}]}

    with pytest.raises(WorkbenchException) as exc:
        verify_pjm_data_miner_definition("rt_hrl_lmps", payload, ROOT / "registries")

    assert exc.value.code == POWER_SYSTEM_SOURCE_METADATA_ERROR
    assert "missing required registry fields" in exc.value.message
    assert "total_lmp_rt" in exc.value.message


def test_approved_source_publication_without_metadata_expectation_fails_closed(tmp_path):
    registry_dir = _copy_metadata_registries(tmp_path)
    price_feeds = yaml.safe_load((registry_dir / "power_system_price_feeds.yaml").read_text(encoding="utf-8"))
    price_feeds.pop("PJM_RT_HOURLY_LMP")
    (registry_dir / "power_system_price_feeds.yaml").write_text(yaml.safe_dump(price_feeds, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_source_metadata_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_SOURCE_METADATA_ERROR
    assert "PJM_RT_HOURLY_LMP" in exc.value.message


def test_verify_pjm_source_metadata_cli_with_fixture_input(tmp_path):
    output = tmp_path / "metadata_report.json"
    expectation = collect_pjm_data_miner_metadata_expectations(ROOT / "registries")["rt_hrl_lmps"]
    input_path = tmp_path / "metadata_fixture.json"
    write_json(input_path, {"feeds": {"rt_hrl_lmps": {"fields": [{"name": field} for field in expectation.required_fields]}}})

    assert (
        main(
            [
                "verify-pjm-source-metadata",
                "--input",
                str(input_path),
                "--feed",
                "rt_hrl_lmps",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    report = read_json(output)
    assert report["definition_source"] == "fixture"
    assert report["verified_feed_count"] == 1
    assert report["verified_feeds"][0]["registry_feed_id"] == "PJM_RT_HOURLY_LMP"


def test_artemis_parser_exposes_pjm_source_metadata_verifier():
    parser = build_artemis_parser()
    args = parser.parse_args(["data-sources", "verify-pjm-metadata", "--input", "metadata.json", "--feed", "rt_hrl_lmps"])

    assert args.func.__name__ == "_cmd_verify_pjm_source_metadata"


def test_artemis_pjm_source_metadata_live_cli_uses_connector_without_network(tmp_path, monkeypatch):
    output = tmp_path / "live_metadata_report.json"
    expectation = collect_pjm_data_miner_metadata_expectations(ROOT / "registries")["rt_hrl_lmps"]

    class FakeConnector:
        def __init__(self, definition_base_url=None):
            self.definition_base_url = definition_base_url

        def fetch_definition(self, feed):
            assert feed == "rt_hrl_lmps"
            return {"fields": [{"name": field} for field in expectation.required_fields]}

    monkeypatch.setattr("pga_workbench.cli.PjmDataMinerConnector", FakeConnector)

    assert (
        artemis_main(
            [
                "data-sources",
                "verify-pjm-metadata",
                "--live",
                "--feed",
                "rt_hrl_lmps",
                "--definition-base-url",
                "https://definition.example",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    report = read_json(output)
    assert report["definition_source"] == "live_pjm_data_miner_definition"
    assert report["verified_feeds"][0]["data_miner_feed"] == "rt_hrl_lmps"
