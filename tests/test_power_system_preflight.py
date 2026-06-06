from __future__ import annotations

from pathlib import Path

from pga_workbench.cli import artemis_main, build_artemis_parser, main
from pga_workbench.serialization import read_json
from pga_workbench.services.power_system_preflight import (
    build_pjm_ingestion_preflight_report,
    selected_pjm_data_miner_metadata_feeds,
)


ROOT = Path(__file__).resolve().parents[1]


def test_pjm_ingestion_preflight_reports_missing_live_prerequisites():
    report = build_pjm_ingestion_preflight_report(
        ROOT / "registries",
        api_key_configured=False,
    )

    assert report["ready"] is False
    assert "ARTEMIS_PJM_API_KEY is not configured" in report["blockers"]
    assert "start and end date window is required for live ingestion planning" in report["blockers"]
    assert "at least one PJM pnode/location is required for live LMP ingestion" in report["blockers"]
    assert report["credential_checks"]["ARTEMIS_PJM_API_KEY"]["value_redacted"] is True


def test_pjm_ingestion_preflight_ready_for_bounded_member_plan():
    report = build_pjm_ingestion_preflight_report(
        ROOT / "registries",
        api_key_configured=True,
        start="2026-06-01",
        end="2026-06-03",
        pnode_count=1,
        account_class="member",
    )

    assert report["ready"] is True
    assert report["blockers"] == []
    assert report["query_plan"]["planned_request_count"] == 7
    assert report["query_plans"]["price"] == report["query_plan"]
    assert report["query_plans"]["load"]["plan_id"] == "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"
    assert report["query_plans"]["load"]["planned_request_count"] == 4
    assert report["query_plans"]["load"]["built_request_count"] == 4
    assert report["query_plans"]["generation_mix"]["plan_id"] == "PJM_DATAMINER_GENERATION_MIX_BOUNDED_INTERVAL"
    assert report["query_plans"]["generation_mix"]["planned_request_count"] == 1
    assert report["source_access_policy"]["max_connections_per_minute"] == 600
    assert "rt_hrl_lmps" in report["selected_feeds"]["metadata_data_miner_feeds"]
    assert "gen_by_fuel" in report["selected_feeds"]["metadata_data_miner_feeds"]


def test_pjm_metadata_feed_selection_includes_pnode_metadata_for_lmp():
    feeds = selected_pjm_data_miner_metadata_feeds(
        ROOT / "registries",
        ["load_frcstd_7_day"],
        ["PJM_RT_HOURLY_LMP"],
        include_generation_mix=False,
    )

    assert feeds == ["load_frcstd_7_day", "pnode", "rt_hrl_lmps"]


def test_pjm_ingestion_preflight_blocks_non_member_over_budget_plan():
    report = build_pjm_ingestion_preflight_report(
        ROOT / "registries",
        api_key_configured=True,
        start="2026-06-01",
        end="2026-06-03",
        pnode_count=1,
        account_class="non_member",
    )

    assert report["ready"] is False
    assert any("requires 7 requests" in blocker for blocker in report["blockers"])
    assert report["query_plan"] is None
    assert report["query_plans"]["load"]["plan_id"] == "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"
    assert report["query_plans"]["generation_mix"]["plan_id"] == "PJM_DATAMINER_GENERATION_MIX_BOUNDED_INTERVAL"


def test_pjm_ingestion_preflight_can_omit_generation_mix_plan():
    report = build_pjm_ingestion_preflight_report(
        ROOT / "registries",
        api_key_configured=True,
        start="2026-06-01",
        end="2026-06-01",
        pnode_count=1,
        account_class="member",
        include_generation_mix=False,
    )

    assert report["ready"] is True
    assert sorted(report["query_plans"]) == ["load", "price"]
    assert report["selected_feeds"]["generation_mix"] == []


def test_pjm_ingestion_preflight_cli_writes_ready_report(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTEMIS_PJM_API_KEY", "fake-key")
    output = tmp_path / "preflight.json"

    assert (
        main(
            [
                "pjm-ingestion-preflight",
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
        == 0
    )

    report = read_json(output)
    assert report["ready"] is True
    assert report["credential_checks"]["ARTEMIS_PJM_API_KEY"]["configured"] is True
    assert "fake-key" not in output.read_text(encoding="utf-8")


def test_pjm_ingestion_preflight_cli_allows_blocked_report(tmp_path, monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    output = tmp_path / "blocked_preflight.json"

    assert main(["pjm-ingestion-preflight", "--allow-blockers", "--output", str(output)]) == 0

    report = read_json(output)
    assert report["ready"] is False
    assert report["blockers"]


def test_artemis_parser_exposes_pjm_ingestion_preflight():
    parser = build_artemis_parser()
    args = parser.parse_args(["data-sources", "pjm-preflight", "--start", "2026-06-01", "--end", "2026-06-02", "--pnode-id", "51288"])

    assert args.func.__name__ == "_cmd_pjm_ingestion_preflight"


def test_artemis_pjm_ingestion_preflight_cli_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTEMIS_PJM_API_KEY", "fake-key")
    output = tmp_path / "artemis_preflight.json"

    assert (
        artemis_main(
            [
                "data-sources",
                "pjm-preflight",
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
        == 0
    )
    assert read_json(output)["ready"] is True
