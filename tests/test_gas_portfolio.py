from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.cli import artemis_main, main
from pga_workbench.registry import validate_registries
from pga_workbench.serialization import read_json
from pga_workbench.services.gas_portfolio import build_sample_gas_portfolio_report, query_gas_portfolio_report


ROOT = Path(__file__).resolve().parents[1]


def test_sample_gas_portfolio_report_contains_through_time_pnl_and_options():
    report = build_sample_gas_portfolio_report()

    assert report["synthetic"] is True
    assert report["source_role"] == "synthetic_test_fixture"
    assert report["as_of_dates"] == ["2026-06-01", "2026-06-02", "2026-06-03"]
    assert len(report["linear_positions_by_as_of"]["2026-06-01"]) == 2
    assert len(report["option_positions_by_as_of"]["2026-06-01"]) == 2
    assert len(report["pnl_periods"]) == 2

    first_period = report["pnl_periods"][0]
    assert first_period["linear_pnl"]["bridge_sums"] is True
    assert first_period["linear_pnl"]["independent_total_effect"] == pytest.approx(41850.0)
    assert first_period["total_option_pnl"] != 0
    assert first_period["total_pnl"] == pytest.approx(first_period["linear_pnl"]["independent_total_effect"] + first_period["total_option_pnl"])

    latest_options = report["option_positions_by_as_of"]["2026-06-03"]
    assert {row["option_contract_id"] for row in latest_options} == {"ICE_PHE_OPTION_HENRY_PENULTIMATE_FIXED_PRICE"}
    assert {row["analytics_scope"] for row in latest_options} == {"screening_only"}
    assert report["local_llm_test"]["forbidden_scope"]


def test_gas_portfolio_query_answers_total_pnl_positions_book_pnl_and_greeks():
    report = build_sample_gas_portfolio_report()

    total = query_gas_portfolio_report(report, "What was total PnL through time?")
    assert total["supported"] is True
    assert total["intent"] == "total_pnl"
    assert len(total["facts"]) == 2
    assert sum(row["total_pnl"] for row in total["facts"]) == pytest.approx(-457280.8959865734)

    positions = query_gas_portfolio_report(report, "What positions did we have on 2026-06-03?")
    assert positions["supported"] is True
    assert positions["facts"]["as_of"] == "2026-06-03"
    assert {row["position_id"] for row in positions["facts"]["linear"]} == {"HH-FUT-N26", "HH-FUT-Q26"}
    assert {row["option_id"] for row in positions["facts"]["options"]} == {"PHE-C-3.25-N26", "PHE-P-3.00-Q326"}

    book = query_gas_portfolio_report(report, "What was book PnL?")
    assert book["supported"] is True
    by_book = {row["book"]: row["pnl"] for row in book["facts"]}
    assert set(by_book) == {"Gas Delta", "Gas Options"}
    assert by_book["Gas Delta"] == pytest.approx(-457250.0)

    greeks = query_gas_portfolio_report(report, "What were the latest option Greeks?")
    assert greeks["supported"] is True
    assert greeks["facts"]["as_of"] == "2026-06-03"
    assert greeks["facts"]["net_delta"] == pytest.approx(1.5614769456601094)
    assert greeks["facts"]["net_vega"] == pytest.approx(0.6971760219259182)


def test_gas_portfolio_query_unsupported_question_fails_closed():
    response = query_gas_portfolio_report(build_sample_gas_portfolio_report(), "Should we buy more gas?")

    assert response["supported"] is False
    assert response["exception"]["code"] == "GAS_PORTFOLIO_QUERY_UNSUPPORTED"
    assert response["agent_scope"] == "local_llm_must_not_invent_missing_facts"


def test_gas_portfolio_cli_build_and_query(tmp_path):
    report_path = tmp_path / "gas_portfolio.json"
    answer_path = tmp_path / "answer.json"

    assert artemis_main(["analyst", "gas-portfolio", "build-sample", "--output", str(report_path)]) == 0
    report = read_json(report_path)
    assert report["scenario_id"] == "synthetic_hh_gas_portfolio_through_time"

    assert (
        artemis_main(
            [
                "analyst",
                "gas-portfolio",
                "query",
                "--input",
                str(report_path),
                "--question",
                "What was total PnL through time?",
                "--output",
                str(answer_path),
            ]
        )
        == 0
    )
    answer = read_json(answer_path)
    assert answer["supported"] is True
    assert answer["intent"] == "total_pnl"

    pga_report_path = tmp_path / "pga_gas_portfolio.json"
    assert main(["build-gas-portfolio-sample", "--output", str(pga_report_path)]) == 0
    assert read_json(pga_report_path)["synthetic"] is True


def test_gas_portfolio_tools_validate_in_registry():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")

    assert "tools.yaml" in result.validated_files
