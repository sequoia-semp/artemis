from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.cli import artemis_main
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.serialization import read_json
from pga_workbench.services.gas_portfolio import build_sample_gas_portfolio_report
from pga_workbench.services.local_llm_portfolio import run_local_llm_portfolio_question
from pga_workbench.services.normalization import normalize_positions
from pga_workbench.services.ports import BuiltinBlack76PricingPort, BuiltinHistoricalRiskPort


def test_builtin_pricing_port_reproduces_black76_option_output():
    port = BuiltinBlack76PricingPort()
    report = port.option_greeks(
        [
            {
                "as_of": "2026-06-04T12:00:00Z",
                "option_symbol": "PHE",
                "option_id": "PHE-P-3.50-N26",
                "delivery_period_id": "N26",
                "option_type": "put",
                "position": "3",
                "forward": "3.5",
                "strike": "3.5",
                "volatility": "0.35",
                "time_to_expiry_years": "0.25",
            }
        ]
    )

    assert port.port_id == "pricing.black76_builtin"
    assert report.greeks[0]["model_price"] == pytest.approx(0.2440407009860075)
    assert report.greeks[0]["position_delta"] == pytest.approx(-1.395411128148854)


def test_builtin_risk_port_reproduces_historical_var_output():
    positions = normalize_positions(
        [
            {
                "as_of": "2026-06-04T12:00:00Z",
                "position_id": "G1",
                "raw_product": "H",
                "raw_period": "N26",
                "raw_quantity": "1",
                "quantity_unit": "contracts",
                "delivery_days": "30",
                "raw_mark": "3",
            }
        ]
    )
    returns = [
        {"date": "d1", "risk_factor": "GAS.HH.LD1.N26", "return": -0.01},
        {"date": "d2", "risk_factor": "GAS.HH.LD1.N26", "return": 0.02},
        {"date": "d3", "risk_factor": "GAS.HH.LD1.N26", "return": -0.05},
    ]

    report = BuiltinHistoricalRiskPort().historical_var(positions, returns, "2026-06-04T12:00:00Z")

    assert report.var_by_confidence["95"] == pytest.approx(11250.0)
    assert report.lineage["risk_factors"] == ["GAS.HH.LD1.N26"]


def test_gas_portfolio_report_lineage_identifies_pricing_port():
    report = build_sample_gas_portfolio_report()

    assert report["lineage"]["ports"]["pricing"]["port_id"] == "pricing.black76_builtin"
    assert "ports.py" in " ".join(report["lineage"]["records"])


def test_local_llm_harness_dry_run_uses_tool_first_and_no_model_call():
    response = run_local_llm_portfolio_question(
        build_sample_gas_portfolio_report(),
        "What was total PnL through time?",
        dry_run=True,
    )

    assert response["tool_first"] is True
    assert response["tool_response"]["supported"] is True
    assert response["provider"]["model_calls"] is False
    assert response["narration"] == response["tool_response"]["answer"]
    assert "DETERMINISTIC_TOOL_RESPONSE" in response["prompt"]


def test_local_llm_harness_keeps_unsupported_questions_unsupported_in_dry_run():
    response = run_local_llm_portfolio_question(
        build_sample_gas_portfolio_report(),
        "Should we buy more gas?",
        dry_run=True,
    )

    assert response["tool_response"]["supported"] is False
    assert response["provider"]["model_calls"] is False
    assert response["narration"].startswith("Unsupported by deterministic tool:")


def test_local_llm_harness_can_call_openai_compatible_endpoint_with_tool_facts():
    calls = []

    def fake_post(url, headers, body, timeout_seconds):
        calls.append((url, headers, body, timeout_seconds))
        return {"choices": [{"message": {"content": "Narrated only from tool facts."}}]}

    response = run_local_llm_portfolio_question(
        build_sample_gas_portfolio_report(),
        "What positions did we have on 2026-06-03?",
        base_url="http://localhost:11434/v1",
        model="local-test-model",
        api_key="test-key",
        http_post=fake_post,
    )

    assert response["provider"]["model_calls"] is True
    assert response["provider"]["model"] == "local-test-model"
    assert response["narration"] == "Narrated only from tool facts."
    assert calls[0][0] == "http://localhost:11434/v1/chat/completions"
    assert calls[0][1]["Authorization"] == "Bearer test-key"
    assert b"DETERMINISTIC_TOOL_RESPONSE" in calls[0][2]


def test_local_llm_harness_requires_explicit_model_for_real_model_call(monkeypatch):
    monkeypatch.delenv("ARTEMIS_OPENAI_COMPATIBLE_MODEL", raising=False)

    with pytest.raises(WorkbenchException) as exc:
        run_local_llm_portfolio_question(
            build_sample_gas_portfolio_report(),
            "What was total PnL through time?",
            dry_run=False,
            base_url="http://localhost:11434/v1",
        )

    assert exc.value.code == "LOCAL_LLM_PORTFOLIO_ERROR"
    assert "pass --model or set ARTEMIS_OPENAI_COMPATIBLE_MODEL" in exc.value.message


def test_local_llm_gas_portfolio_cli_dry_run(tmp_path: Path):
    report_path = tmp_path / "report.json"
    answer_path = tmp_path / "local_llm_answer.json"

    assert artemis_main(["analyst", "gas-portfolio", "build-sample", "--output", str(report_path)]) == 0
    assert (
        artemis_main(
            [
                "analyst",
                "gas-portfolio",
                "ask-local-llm",
                "--input",
                str(report_path),
                "--question",
                "What was total PnL through time?",
                "--output",
                str(answer_path),
                "--dry-run",
            ]
        )
        == 0
    )

    payload = read_json(answer_path)
    assert payload["tool_first"] is True
    assert payload["provider"]["kind"] == "deterministic_dry_run"
    assert payload["tool_response"]["intent"] == "total_pnl"
