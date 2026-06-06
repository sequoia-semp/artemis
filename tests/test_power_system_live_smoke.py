from __future__ import annotations

from pathlib import Path

from pga_workbench.cli import artemis_main, build_artemis_parser, main
from pga_workbench.data.contracts import DataRequest, DataResult
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.serialization import read_json
from pga_workbench.services.power_system_live_smoke import build_pjm_live_smoke_report, validate_power_system_source_readiness_report
from pga_workbench.services.power_system_preflight import (
    DEFAULT_PJM_LOAD_FEEDS,
    DEFAULT_PJM_PRICE_FEEDS,
    selected_pjm_data_miner_metadata_feeds,
)
from pga_workbench.services.power_system_source_metadata import collect_pjm_data_miner_metadata_expectations


ROOT = Path(__file__).resolve().parents[1]


class FakeSmokeConnector:
    account_class = "member"

    def __init__(self, available: bool = True, fail_contract: str | None = None):
        self._available = available
        self.fail_contract = fail_contract
        self.requests: list[DataRequest] = []
        self.definitions = []

    def available(self) -> bool:
        return self._available

    def fetch_definition(self, feed: str) -> dict:
        expectations = collect_pjm_data_miner_metadata_expectations(ROOT / "registries")
        self.definitions.append(feed)
        return {"fields": [{"name": field} for field in expectations[feed].required_fields]}

    def fetch(self, request: DataRequest) -> DataResult:
        self.requests.append(request)
        if request.contract == self.fail_contract:
            raise WorkbenchException("PJM_TEST_SOURCE_TIMEOUT", f"{request.contract} timed out")
        return DataResult(
            source="PJM Data Miner",
            contract=request.contract,
            data_environment="production",
            records=[{"ok": True}],
            lineage={"page_count": 1, "truncated_by_max_pages": False},
        )


def test_pjm_live_smoke_reports_missing_prerequisites_without_source_fetch():
    connector = FakeSmokeConnector(available=False)

    report = build_pjm_live_smoke_report(
        ROOT / "registries",
        connector,
        fetch_source_rows=True,
    )

    assert report["ready"] is False
    assert "ARTEMIS_PJM_API_KEY is not configured" in report["blockers"]
    assert report["preflight"]["credential_checks"]["ARTEMIS_PJM_API_KEY"]["value_redacted"] is True
    assert report["metadata_verification"]["verified_feed_count"] == len(
        selected_pjm_data_miner_metadata_feeds(
            ROOT / "registries",
            DEFAULT_PJM_LOAD_FEEDS,
            DEFAULT_PJM_PRICE_FEEDS,
            include_generation_mix=True,
        )
    )
    assert report["source_fetches"] == []
    assert connector.requests == []
    assert report["contains_secret_values"] is False


def test_pjm_live_smoke_fetches_bounded_rows_after_preflight_and_metadata():
    connector = FakeSmokeConnector()

    report = build_pjm_live_smoke_report(
        ROOT / "registries",
        connector,
        start="2026-06-01",
        end="2026-06-01",
        pnode_ids=[51288],
        load_feeds=["load_frcstd_7_day"],
        price_feeds=["PJM_RT_HOURLY_LMP"],
        include_generation_mix=True,
        fetch_source_rows=True,
    )

    assert report["ready"] is True
    assert [item["data_miner_feed"] for item in report["source_fetches"]] == [
        "load_frcstd_7_day",
        "pnode",
        "rt_hrl_lmps",
        "gen_by_fuel",
    ]
    validate_power_system_source_readiness_report(report, ROOT / "schemas")
    assert all(item["status"] == "success" for item in report["source_fetches"])
    assert all(item["row_count"] == 1 for item in report["source_fetches"])
    assert all(request.parameters["query"]["rowCount"] == 1 for request in connector.requests)
    assert all(request.parameters["paginate"] is False for request in connector.requests)
    assert report["query_execution"] == {
        "plan_id": "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS",
        "planned_request_count": 2,
        "built_request_count": 2,
        "account_class": "member",
        "max_connections_per_minute": 600,
        "request_kinds": {"metadata": 1, "source_rows": 1},
        "registry_feed_ids": ["PJM_PNODE", "PJM_RT_HOURLY_LMP"],
        "pnode_ids": [51288],
        "date_windows": [{"start": "2026-06-01", "end": "2026-06-01"}],
        "contains_secret_values": False,
    }
    price_request = next(request for request in connector.requests if request.contract == "PJM_RT_HOURLY_LMP")
    assert price_request.parameters["query"]["sort"] == "datetime_beginning_ept"
    assert price_request.parameters["query_execution_summary"] == report["query_execution"]
    assert price_request.parameters["query_request"]["request_id"] == "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS.PJM_RT_HOURLY_LMP.51288.2026-06-01"


def test_pjm_live_smoke_records_source_fetch_errors_as_blockers():
    connector = FakeSmokeConnector(fail_contract="PJM_GEN_BY_FUEL")

    report = build_pjm_live_smoke_report(
        ROOT / "registries",
        connector,
        start="2026-06-01",
        end="2026-06-01",
        pnode_ids=[51288],
        load_feeds=["load_frcstd_7_day"],
        price_feeds=["PJM_RT_HOURLY_LMP"],
        include_generation_mix=True,
        fetch_source_rows=True,
    )

    generation = report["source_fetches"][-1]
    assert report["ready"] is False
    assert "gen_by_fuel (PJM_TEST_SOURCE_TIMEOUT)" in report["blockers"][0]
    assert generation["status"] == "error"
    assert generation["data_miner_feed"] == "gen_by_fuel"
    assert generation["row_count"] == 0
    assert generation["error_code"] == "PJM_TEST_SOURCE_TIMEOUT"
    assert "Ocp-Apim-Subscription-Key" not in str(generation)
    assert [item["status"] for item in report["source_fetches"][:3]] == ["success", "success", "success"]
    validate_power_system_source_readiness_report(report, ROOT / "schemas")


def test_power_system_source_readiness_schema_rejects_unredacted_report():
    connector = FakeSmokeConnector()
    report = build_pjm_live_smoke_report(
        ROOT / "registries",
        connector,
        start="2026-06-01",
        end="2026-06-01",
        pnode_ids=[51288],
        load_feeds=["load_frcstd_7_day"],
        price_feeds=["PJM_RT_HOURLY_LMP"],
        include_generation_mix=False,
        fetch_source_rows=True,
    )
    report["contains_secret_values"] = True

    try:
        validate_power_system_source_readiness_report(report, ROOT / "schemas")
    except WorkbenchException as exc:
        assert exc.code == "POWER_SYSTEM_LIVE_SMOKE_ERROR"
        assert "contains_secret_values" in exc.message
    else:
        raise AssertionError("readiness schema should reject reports that claim to contain secret values")


def test_pjm_live_smoke_cli_writes_redacted_report(tmp_path, monkeypatch):
    output = tmp_path / "pjm_live_smoke.json"

    class FakeCliConnector(FakeSmokeConnector):
        def __init__(self, base_url=None, definition_base_url=None, timeout_seconds=30.0):
            super().__init__(available=True)
            self.base_url = base_url
            self.definition_base_url = definition_base_url
            self.timeout_seconds = timeout_seconds

    monkeypatch.setattr("pga_workbench.cli.PjmDataMinerConnector", FakeCliConnector)

    assert (
        main(
            [
                "pjm-live-smoke",
                "--start",
                "2026-06-01",
                "--end",
                "2026-06-01",
                "--pnode-id",
                "51288",
                "--load-feed",
                "load_frcstd_7_day",
                "--price-feed",
                "PJM_RT_HOURLY_LMP",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    report = read_json(output)
    assert report["ready"] is True
    assert report["contains_secret_values"] is False
    assert "Ocp-Apim-Subscription-Key" not in output.read_text(encoding="utf-8")


def test_artemis_parser_exposes_pjm_live_smoke():
    parser = build_artemis_parser()
    args = parser.parse_args(["data-sources", "pjm-live-smoke", "--start", "2026-06-01", "--end", "2026-06-01", "--pnode-id", "51288"])

    assert args.func.__name__ == "_cmd_pjm_live_smoke"


def test_artemis_pjm_live_smoke_cli_smoke(tmp_path, monkeypatch):
    output = tmp_path / "artemis_pjm_live_smoke.json"

    class FakeCliConnector(FakeSmokeConnector):
        def __init__(self, base_url=None, definition_base_url=None, timeout_seconds=30.0):
            super().__init__(available=True)

    monkeypatch.setattr("pga_workbench.cli.PjmDataMinerConnector", FakeCliConnector)

    assert (
        artemis_main(
            [
                "data-sources",
                "pjm-live-smoke",
                "--start",
                "2026-06-01",
                "--end",
                "2026-06-01",
                "--pnode-id",
                "51288",
                "--metadata-only",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert read_json(output)["fetch_source_rows"] is False
