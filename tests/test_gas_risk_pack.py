from __future__ import annotations

from pathlib import Path

from pga_workbench.agent_runtime.kb_validator import validate_knowledge_base
from pga_workbench.cli import artemis_main
from pga_workbench.registry import validate_registries
from pga_workbench.serialization import read_json
from pga_workbench.services.gas_portfolio import build_sample_gas_portfolio_report
from pga_workbench.services.gas_risk_pack import build_cached_gas_risk_pack, query_gas_risk_pack
from pga_workbench.services.local_llm_portfolio import run_local_llm_gas_risk_pack_question


ROOT = Path(__file__).resolve().parents[1]


def test_gas_risk_pack_builds_materialized_metrics_and_reuses_cache(tmp_path: Path):
    report = build_sample_gas_portfolio_report()

    first = build_cached_gas_risk_pack(report, "2026-06-03", tmp_path, force=True)
    second = build_cached_gas_risk_pack(report, "2026-06-03", tmp_path)

    assert first["cache_status"] == "rebuilt"
    assert second["cache_status"] == "hit"
    assert second["manifest"]["cache_key"] == first["manifest"]["cache_key"]
    assert (tmp_path / "gas/2026-06-03/gas_risk_pack.json").exists()

    risk = first["risk"]
    assert risk["exposure_buckets"]["by_period"]
    assert risk["historical_var_expected_shortfall"]["metrics"]["95"]["var"] > 0
    assert risk["stress_scenarios"]
    assert risk["option_pnl_explain"]["available"] is True
    assert first["strategy_semantics"]["approval_status"] == "human_review_required"
    assert first["definitions"]["strategy_labels"] == "reporting metadata only unless separately human-approved"


def test_gas_risk_pack_queries_answer_only_from_materialized_pack():
    pack = build_cached_gas_risk_pack(build_sample_gas_portfolio_report(), "2026-06-03", Path("/tmp/test-gas-risk-pack-query"), force=True)

    exposure = query_gas_risk_pack(pack, "Show exposure buckets")
    assert exposure["supported"] is True
    assert exposure["intent"] == "exposure_buckets"
    assert exposure["facts"] == pack["query_index"]["exposure_buckets"]

    var_es = query_gas_risk_pack(pack, "What is 95% VaR and expected shortfall?")
    assert var_es["supported"] is True
    assert var_es["intent"] == "var_expected_shortfall"

    stress = query_gas_risk_pack(pack, "What is the worst stress scenario?")
    assert stress["supported"] is True
    assert stress["intent"] == "stress_scenarios"
    assert "parallel_down_20c" in stress["answer"]

    option_explain = query_gas_risk_pack(pack, "Explain option PnL")
    assert option_explain["supported"] is True
    assert option_explain["intent"] == "option_pnl_explain"

    strategy = query_gas_risk_pack(pack, "Are straddles approved?")
    assert strategy["supported"] is True
    assert strategy["intent"] == "strategy_semantics"
    assert strategy["facts"]["approval_status"] == "human_review_required"
    assert strategy["facts"]["authority"] == "advisory_reporting_metadata_only"

    unsupported = query_gas_risk_pack(pack, "Should we buy more gas?")
    assert unsupported["supported"] is False
    assert unsupported["exception"]["code"] == "GAS_RISK_QUERY_UNSUPPORTED"
    assert unsupported["agent_scope"] == "local_llm_must_not_invent_missing_facts"


def test_local_llm_gas_risk_pack_dry_run_uses_tool_first_response(tmp_path: Path):
    pack = build_cached_gas_risk_pack(build_sample_gas_portfolio_report(), "2026-06-03", tmp_path, force=True)

    response = run_local_llm_gas_risk_pack_question(pack, "What is the worst stress scenario?", dry_run=True)

    assert response["tool_first"] is True
    assert response["provider"]["kind"] == "deterministic_dry_run"
    assert response["tool_response"]["intent"] == "stress_scenarios"
    assert response["narration"] == response["tool_response"]["answer"]


def test_gas_risk_pack_cli_build_query_and_llm_dry_run(tmp_path: Path):
    report_path = tmp_path / "gas_portfolio.json"
    pack_path = tmp_path / "gas_risk_pack.json"
    answer_path = tmp_path / "answer.json"
    llm_path = tmp_path / "llm.json"

    assert artemis_main(["analyst", "gas-portfolio", "build-sample", "--output", str(report_path)]) == 0
    assert (
        artemis_main(
            [
                "analyst",
                "gas-risk",
                "build",
                "--portfolio-report",
                str(report_path),
                "--as-of",
                "2026-06-03",
                "--output-root",
                str(tmp_path / "risk-cache"),
                "--output",
                str(pack_path),
            ]
        )
        == 0
    )
    assert read_json(pack_path)["manifest"]["risk_pack_version"] == "gas_risk_pack_v0.1"

    assert (
        artemis_main(
            [
                "analyst",
                "gas-risk",
                "query",
                "--input",
                str(pack_path),
                "--question",
                "What is the worst stress scenario?",
                "--output",
                str(answer_path),
            ]
        )
        == 0
    )
    assert read_json(answer_path)["intent"] == "stress_scenarios"

    assert (
        artemis_main(
            [
                "analyst",
                "gas-risk",
                "ask-local-llm",
                "--input",
                str(pack_path),
                "--question",
                "Are straddles approved?",
                "--output",
                str(llm_path),
                "--dry-run",
            ]
        )
        == 0
    )
    payload = read_json(llm_path)
    assert payload["provider"]["model_calls"] is False
    assert payload["tool_response"]["facts"]["approval_status"] == "human_review_required"


def test_gas_risk_pack_tools_and_candidate_kb_validate():
    registry_result = validate_registries(ROOT / "registries", ROOT / "schemas")
    kb_result = validate_knowledge_base(ROOT / "knowledge_base", ROOT / "schemas")

    assert "tools.yaml" in registry_result.validated_files
    assert kb_result["entries"] == 5
