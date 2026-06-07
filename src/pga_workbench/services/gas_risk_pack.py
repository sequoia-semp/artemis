from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..core.time import utc_now_iso
from ..exceptions import WorkbenchException
from ..serialization import read_json, write_json

GAS_RISK_PACK_ERROR = "GAS_RISK_PACK_ERROR"
GAS_RISK_QUERY_UNSUPPORTED = "GAS_RISK_QUERY_UNSUPPORTED"

RISK_PACK_VERSION = "gas_risk_pack_v0.1"
RISK_POLICY_VERSION = "synthetic_hh_risk_policy_v0.1"
STRATEGY_SEMANTICS_VERSION = "candidate_reporting_labels_v0.1"

SUPPORTED_REPORTING_LABELS = {
    "outright",
    "calendar",
    "vol",
    "straddle",
    "costless_collar",
    "25d_rr",
    "breakeven",
}


def build_cached_gas_risk_pack(
    portfolio_report: dict[str, Any],
    as_of: str,
    output_root: Path,
    *,
    force: bool = False,
    run_id: str = "gas-risk-pack",
) -> dict[str, Any]:
    output_root = Path(output_root)
    pack_path = gas_risk_pack_path(output_root, as_of)
    cache_key = _cache_key(portfolio_report, as_of)
    if pack_path.exists() and not force:
        existing = read_json(pack_path)
        if ((existing.get("manifest") or {}).get("cache_key")) == cache_key:
            existing["cache_status"] = "hit"
            return existing

    pack = build_gas_risk_pack(portfolio_report, as_of, run_id=run_id, cache_key=cache_key)
    pack["cache_status"] = "rebuilt"
    write_json(pack_path, pack)
    return pack


def gas_risk_pack_path(output_root: Path, as_of: str) -> Path:
    return Path(output_root) / "gas" / as_of / "gas_risk_pack.json"


def build_gas_risk_pack(
    portfolio_report: dict[str, Any],
    as_of: str,
    *,
    run_id: str = "gas-risk-pack",
    cache_key: str | None = None,
) -> dict[str, Any]:
    _require_as_of(portfolio_report, as_of)
    prior_as_of = _prior_as_of(portfolio_report, as_of)
    linear = list(portfolio_report["linear_positions_by_as_of"][as_of])
    options = list(portfolio_report["option_positions_by_as_of"][as_of])
    exposure_buckets = _exposure_buckets(linear, options)
    scenario_returns = _synthetic_factor_returns(exposure_buckets["risk_factors"])
    var_es = _historical_var_expected_shortfall(exposure_buckets["factor_exposures"], scenario_returns)
    stress = _stress_scenarios(exposure_buckets["factor_exposures"], options)
    option_explain = _option_pnl_explain(portfolio_report, prior_as_of, as_of)
    query_index = _query_index(as_of, exposure_buckets, var_es, stress, option_explain)
    strategy_semantics = _strategy_semantics(linear, options)

    manifest = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "as_of": as_of,
        "portfolio_run_id": portfolio_report.get("run_id"),
        "portfolio_scenario_id": portfolio_report.get("scenario_id"),
        "risk_pack_version": RISK_PACK_VERSION,
        "risk_policy_version": RISK_POLICY_VERSION,
        "strategy_semantics_version": STRATEGY_SEMANTICS_VERSION,
        "cache_key": cache_key or _cache_key(portfolio_report, as_of),
        "synthetic": bool(portfolio_report.get("synthetic")),
        "source_role": portfolio_report.get("source_role"),
    }
    return {
        "run_id": run_id,
        "as_of": as_of,
        "prior_as_of": prior_as_of,
        "manifest": manifest,
        "positions": {
            "linear": linear,
            "options": options,
        },
        "valuations": {
            "total_market_value": _summary_for_as_of(portfolio_report, as_of)["total_market_value"],
            "linear_market_value": _summary_for_as_of(portfolio_report, as_of)["linear_market_value"],
            "option_market_value": _summary_for_as_of(portfolio_report, as_of)["option_market_value"],
        },
        "risk": {
            "exposure_buckets": exposure_buckets,
            "historical_var_expected_shortfall": var_es,
            "stress_scenarios": stress,
            "option_pnl_explain": option_explain,
        },
        "query_index": query_index,
        "strategy_semantics": strategy_semantics,
        "definitions": _definitions(),
        "lineage": {
            "records": [
                "src/pga_workbench/services/gas_risk_pack.py",
                "src/pga_workbench/services/gas_portfolio.py",
                "domain/period_grammar.md",
                "domain/vol_surface_conventions.md",
                "docs/analyst/gas_strategy_semantics.md",
            ],
            "cache_policy": "immutable_daily_pack_reused_when_cache_key_matches",
            "non_authority_notes": [
                "Synthetic risk pack is local-test only.",
                "Strategy labels are reporting metadata unless separately human-approved.",
            ],
        },
    }


def query_gas_risk_pack(pack: dict[str, Any], question: str, run_id: str = "gas-risk-query") -> dict[str, Any]:
    q = question.strip()
    lowered = q.lower()
    if not q:
        raise WorkbenchException(GAS_RISK_QUERY_UNSUPPORTED, "Question is required")
    if any(term in lowered for term in ["exposure", "bucket", "mmbtu"]):
        return _supported(q, run_id, "exposure_buckets", _exposure_answer(pack), pack["query_index"]["exposure_buckets"], ["risk.exposure_buckets"])
    if any(term in lowered for term in ["stress", "shock", "scenario"]):
        return _supported(q, run_id, "stress_scenarios", _stress_answer(pack), pack["query_index"]["stress_scenarios"], ["risk.stress_scenarios"])
    if "var" in lowered or "expected shortfall" in lowered or re.search(r"\bes\b", lowered) or "risk metric" in lowered:
        return _supported(q, run_id, "var_expected_shortfall", _var_answer(pack), pack["query_index"]["historical_var_expected_shortfall"], ["risk.historical_var_expected_shortfall"])
    if any(term in lowered for term in ["option explain", "option pnl", "vega pnl", "gamma pnl", "theta"]):
        return _supported(q, run_id, "option_pnl_explain", _option_explain_answer(pack), pack["query_index"]["option_pnl_explain"], ["risk.option_pnl_explain"])
    if any(term in lowered for term in ["cache", "lineage", "definition", "definitions"]):
        facts = {
            "manifest": pack["manifest"],
            "lineage": pack["lineage"],
            "definitions": pack["definitions"],
        }
        return _supported(q, run_id, "cache_lineage_definitions", "Risk pack cache, lineage, and definitions are materialized in the returned facts.", facts, ["manifest", "lineage", "definitions"])
    if any(term in lowered for term in ["strategy", "straddle", "collar", "25d", "risk reversal", "breakeven", "xh", "jv", "approved", "approval"]):
        return _supported(q, run_id, "strategy_semantics", _strategy_answer(pack), pack["strategy_semantics"], ["strategy_semantics"])
    return _unsupported(q, run_id)


def _cache_key(portfolio_report: dict[str, Any], as_of: str) -> str:
    payload = {
        "as_of": as_of,
        "portfolio": {
            "linear": portfolio_report["linear_positions_by_as_of"].get(as_of),
            "options": portfolio_report["option_positions_by_as_of"].get(as_of),
            "pnl_periods": portfolio_report.get("pnl_periods"),
        },
        "risk_pack_version": RISK_PACK_VERSION,
        "risk_policy_version": RISK_POLICY_VERSION,
        "strategy_semantics_version": STRATEGY_SEMANTICS_VERSION,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_as_of(report: dict[str, Any], as_of: str) -> None:
    if as_of not in report.get("as_of_dates", []):
        raise WorkbenchException(GAS_RISK_PACK_ERROR, f"Portfolio report has no as_of date: {as_of}")


def _prior_as_of(report: dict[str, Any], as_of: str) -> str | None:
    dates = list(report.get("as_of_dates") or [])
    index = dates.index(as_of)
    return None if index == 0 else str(dates[index - 1])


def _summary_for_as_of(report: dict[str, Any], as_of: str) -> dict[str, Any]:
    for item in report.get("summaries") or []:
        if item.get("as_of") == as_of:
            return item
    raise WorkbenchException(GAS_RISK_PACK_ERROR, f"Portfolio report summary missing for {as_of}")


def _exposure_buckets(linear: list[dict[str, Any]], options: list[dict[str, Any]]) -> dict[str, Any]:
    factor_exposures: dict[str, float] = {}
    by_period: dict[str, dict[str, Any]] = {}
    by_strategy: dict[str, dict[str, Any]] = {}
    for row in linear:
        period = str(row["position_lot"]["period_id"])
        factor = str(row["normalized"]["index_id"])
        mmbtu = float(row["derived"]["derived_MMBtu"] or 0.0)
        market_value = float(row["derived"]["market_value"] or 0.0)
        strategy = str(row["identity"].get("strategy") or "unassigned")
        factor_exposures[factor] = factor_exposures.get(factor, 0.0) + market_value
        _bucket_add(by_period, period, "linear_mmbtu", mmbtu)
        _bucket_add(by_period, period, "linear_market_value", market_value)
        _bucket_add(by_strategy, strategy, "linear_mmbtu", mmbtu)
        _bucket_add(by_strategy, strategy, "linear_market_value", market_value)
    for row in options:
        period = str(row["delivery_period_id"])
        factor = f"{row['underlying_index_id']}.{period}"
        delta_mmbtu = float(row["position_delta"]) * float(row["contract_size_mmbtu"])
        vega_usd_per_abs_vol = float(row["position_vega"]) * float(row["contract_size_mmbtu"])
        strategy = str(row.get("strategy") or "unassigned")
        factor_exposures[factor] = factor_exposures.get(factor, 0.0) + delta_mmbtu * float(row["forward"])
        _bucket_add(by_period, period, "option_delta_mmbtu", delta_mmbtu)
        _bucket_add(by_period, period, "option_vega_usd_per_abs_vol", vega_usd_per_abs_vol)
        _bucket_add(by_strategy, strategy, "option_delta_mmbtu", delta_mmbtu)
        _bucket_add(by_strategy, strategy, "option_vega_usd_per_abs_vol", vega_usd_per_abs_vol)
    return {
        "risk_factors": sorted(factor_exposures),
        "factor_exposures": [{"risk_factor": key, "exposure_value": value} for key, value in sorted(factor_exposures.items())],
        "by_period": _bucket_rows(by_period, "period_id"),
        "by_strategy": _bucket_rows(by_strategy, "strategy"),
        "definitions": {
            "linear_mmbtu": "signed futures contract quantity converted with 2500 MMBtu/day and delivery_days from the position",
            "option_delta_mmbtu": "Black-76 position_delta multiplied by option contract_size_mmbtu",
            "option_vega_usd_per_abs_vol": "Black-76 position_vega multiplied by option contract_size_mmbtu; volatility shock unit is 1.00 absolute volatility",
        },
    }


def _bucket_add(buckets: dict[str, dict[str, Any]], key: str, field: str, value: float) -> None:
    row = buckets.setdefault(key, {})
    row[field] = float(row.get(field) or 0.0) + value


def _bucket_rows(buckets: dict[str, dict[str, Any]], key_name: str) -> list[dict[str, Any]]:
    fields = ["linear_mmbtu", "linear_market_value", "option_delta_mmbtu", "option_vega_usd_per_abs_vol"]
    rows = []
    for key, values in sorted(buckets.items()):
        row = {key_name: key}
        for field in fields:
            row[field] = float(values.get(field) or 0.0)
        row["total_delta_equivalent_mmbtu"] = row["linear_mmbtu"] + row["option_delta_mmbtu"]
        rows.append(row)
    return rows


def _synthetic_factor_returns(risk_factors: list[str]) -> list[dict[str, Any]]:
    base = [
        ("hist-1", -0.025),
        ("hist-2", 0.015),
        ("hist-3", -0.040),
        ("hist-4", 0.030),
        ("hist-5", -0.010),
    ]
    rows = []
    for date, value in base:
        for factor in risk_factors:
            period_adjustment = 0.8 if "Q3" in factor else 1.0
            rows.append({"date": date, "risk_factor": factor, "return": value * period_adjustment})
    return rows


def _historical_var_expected_shortfall(factor_exposures: list[dict[str, Any]], returns: list[dict[str, Any]]) -> dict[str, Any]:
    exposure = {str(row["risk_factor"]): float(row["exposure_value"]) for row in factor_exposures}
    scenario_pnl: dict[str, float] = {}
    for row in returns:
        factor = str(row["risk_factor"])
        scenario_pnl[str(row["date"])] = scenario_pnl.get(str(row["date"]), 0.0) + exposure[factor] * float(row["return"])
    scenario_rows = [{"date": date, "pnl": pnl} for date, pnl in sorted(scenario_pnl.items())]
    sorted_pnl = sorted(float(row["pnl"]) for row in scenario_rows)
    metrics = {}
    for confidence in [0.95, 0.99]:
        index = int((1.0 - confidence) * (len(sorted_pnl) - 1))
        tail = sorted_pnl[: index + 1]
        var_value = max(0.0, -sorted_pnl[index])
        es_value = max(0.0, -sum(tail) / len(tail))
        metrics[str(int(confidence * 100))] = {"var": var_value, "expected_shortfall": es_value}
    return {
        "method": "historical_simulation_delta_approx",
        "confidence_levels": [0.95, 0.99],
        "lookback_observations": len(scenario_rows),
        "metrics": metrics,
        "scenario_pnl": scenario_rows,
        "input_returns": returns,
        "definitions": {
            "var": "positive loss threshold from sorted historical scenario PnL",
            "expected_shortfall": "average positive loss across scenarios at or beyond the VaR tail index",
        },
    }


def _stress_scenarios(factor_exposures: list[dict[str, Any]], options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    delta_by_factor = {str(row["risk_factor"]): float(row["exposure_value"]) for row in factor_exposures}
    scenarios = [
        {"scenario_id": "parallel_up_20c", "price_shock": 0.20, "vol_shock": 0.0, "selector": "all"},
        {"scenario_id": "parallel_down_20c", "price_shock": -0.20, "vol_shock": 0.0, "selector": "all"},
        {"scenario_id": "prompt_spike_50c", "price_shock": 0.50, "vol_shock": 0.0, "selector": "prompt"},
        {"scenario_id": "vol_up_5pts", "price_shock": 0.0, "vol_shock": 0.05, "selector": "options"},
        {"scenario_id": "combined_down_20c_vol_up_5pts", "price_shock": -0.20, "vol_shock": 0.05, "selector": "all"},
    ]
    rows = []
    option_vega = sum(float(row["position_vega"]) * float(row["contract_size_mmbtu"]) for row in options)
    for scenario in scenarios:
        selector = str(scenario["selector"])
        price_pnl = 0.0
        for factor, exposure_value in delta_by_factor.items():
            if selector == "prompt" and not factor.endswith(".N26"):
                continue
            if selector == "options":
                continue
            # Exposure value is dollar-value-like for VaR. Convert price shock to
            # a relative return against a stable HH reference for the synthetic pack.
            price_pnl += exposure_value * float(scenario["price_shock"]) / 3.0
        vol_pnl = option_vega * float(scenario["vol_shock"])
        rows.append(
            {
                **scenario,
                "price_pnl": price_pnl,
                "vol_pnl": vol_pnl,
                "total_pnl": price_pnl + vol_pnl,
                "definition": "synthetic deterministic stress using delta-equivalent exposure and Black-76 vega approximation",
            }
        )
    return rows


def _option_pnl_explain(report: dict[str, Any], prior_as_of: str | None, as_of: str) -> dict[str, Any]:
    if prior_as_of is None:
        return {"available": False, "reason": "No prior as_of date for option PnL explain", "rows": []}
    prior = {row["option_id"]: row for row in report["option_positions_by_as_of"][prior_as_of]}
    current = {row["option_id"]: row for row in report["option_positions_by_as_of"][as_of]}
    rows = []
    for option_id in sorted(set(prior) | set(current)):
        p0 = prior.get(option_id)
        p1 = current.get(option_id)
        prior_value = float(p0["market_value"]) if p0 else 0.0
        current_value = float(p1["market_value"]) if p1 else 0.0
        actual = current_value - prior_value
        if not p0 or not p1:
            rows.append({"option_id": option_id, "actual_pnl": actual, "explained_pnl": 0.0, "residual": actual, "reason": "new_or_expired_option"})
            continue
        contract_size = float(p0["contract_size_mmbtu"])
        d_forward = float(p1["forward"]) - float(p0["forward"])
        d_vol = float(p1["volatility"]) - float(p0["volatility"])
        elapsed_years = max(0.0, float(p0["time_to_expiry_years"]) - float(p1["time_to_expiry_years"]))
        delta_pnl = float(p0["position_delta"]) * contract_size * d_forward
        gamma_pnl = 0.5 * float(p0["position_gamma"]) * contract_size * d_forward * d_forward
        vega_pnl = float(p0["position_vega"]) * contract_size * d_vol
        theta_pnl = float(p0["position_theta"]) * contract_size * elapsed_years
        explained = delta_pnl + gamma_pnl + vega_pnl + theta_pnl
        rows.append(
            {
                "option_id": option_id,
                "actual_pnl": actual,
                "delta_pnl": delta_pnl,
                "gamma_pnl": gamma_pnl,
                "vega_pnl": vega_pnl,
                "theta_pnl": theta_pnl,
                "explained_pnl": explained,
                "residual": actual - explained,
                "definition": "first/second order Black-76 explain using prior-day Greeks; residual remains explicit",
            }
        )
    return {
        "available": True,
        "prior_as_of": prior_as_of,
        "current_as_of": as_of,
        "rows": rows,
        "totals": {
            "actual_pnl": sum(float(row["actual_pnl"]) for row in rows),
            "explained_pnl": sum(float(row.get("explained_pnl") or 0.0) for row in rows),
            "residual": sum(float(row.get("residual") or 0.0) for row in rows),
        },
    }


def _query_index(as_of: str, exposure_buckets: dict[str, Any], var_es: dict[str, Any], stress: list[dict[str, Any]], option_explain: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of": as_of,
        "exposure_buckets": {
            "by_period": exposure_buckets["by_period"],
            "by_strategy": exposure_buckets["by_strategy"],
        },
        "historical_var_expected_shortfall": {
            "method": var_es["method"],
            "metrics": var_es["metrics"],
        },
        "stress_scenarios": [{"scenario_id": row["scenario_id"], "total_pnl": row["total_pnl"]} for row in stress],
        "option_pnl_explain": option_explain.get("totals") or {"available": False},
    }


def _strategy_semantics(linear: list[dict[str, Any]], options: list[dict[str, Any]]) -> dict[str, Any]:
    observed = sorted({str(row["identity"].get("strategy")) for row in linear} | {str(row.get("strategy")) for row in options})
    standard_candidates = ["XH", "JV", "H/J", "V/F", "straddle", "costless_collar", "25d_rr", "breakeven"]
    return {
        "approval_status": "human_review_required",
        "authority": "advisory_reporting_metadata_only",
        "observed_strategy_labels": observed,
        "standard_candidate_labels": standard_candidates,
        "locked_period_labels": {
            "XH": "gas winter Nov-Mar per domain/period_grammar.md",
            "JV": "gas summer Apr-Oct per domain/period_grammar.md",
            "month_codes": "F,G,H,J,K,M,N,Q,U,V,X,Z per domain/period_grammar.md",
        },
        "unapproved_structure_labels": {
            "straddle": "reporting label only until human-approved option-structure convention exists",
            "costless_collar": "reporting label only until human-approved option-structure convention exists",
            "25d_rr": "reporting label only until human-approved delta/skew convention exists",
            "breakeven": "reporting label only until human-approved breakeven convention exists",
        },
        "knowledge_base_entry": "knowledge_base/market_conventions/gas_strategy_labels_candidate.md",
    }


def _definitions() -> dict[str, Any]:
    return {
        "cache_key": "sha256 of as_of positions/options, PnL periods, risk pack version, risk policy version, and strategy semantics version",
        "historical_var": "delta-approx historical simulation on materialized factor exposures and synthetic fixture returns",
        "expected_shortfall": "average tail loss at or beyond VaR tail index",
        "stress": "deterministic synthetic shock grid; not a market convention or recommendation",
        "option_pnl_explain": "approximate explain using prior-day Black-76 Greeks with explicit residual",
        "strategy_labels": "reporting metadata only unless separately human-approved",
    }


def _exposure_answer(pack: dict[str, Any]) -> str:
    rows = pack["query_index"]["exposure_buckets"]["by_period"]
    return f"Risk pack {pack['as_of']} has exposure buckets for {len(rows)} periods."


def _var_answer(pack: dict[str, Any]) -> str:
    metrics = pack["query_index"]["historical_var_expected_shortfall"]["metrics"]
    return f"Historical 95% VaR is {metrics['95']['var']:.2f} USD and 95% expected shortfall is {metrics['95']['expected_shortfall']:.2f} USD."


def _stress_answer(pack: dict[str, Any]) -> str:
    worst = min(pack["query_index"]["stress_scenarios"], key=lambda row: float(row["total_pnl"]))
    return f"Worst configured stress is {worst['scenario_id']} with PnL {worst['total_pnl']:.2f} USD."


def _option_explain_answer(pack: dict[str, Any]) -> str:
    totals = pack["query_index"]["option_pnl_explain"]
    if totals.get("available") is False:
        return "Option PnL explain is not available for the first risk-pack date."
    return f"Option actual PnL is {totals['actual_pnl']:.2f} USD with residual {totals['residual']:.2f} USD."


def _strategy_answer(pack: dict[str, Any]) -> str:
    return "Strategy and option-structure labels are advisory reporting metadata and require human review before becoming conventions."


def _supported(question: str, run_id: str, intent: str, answer: str, facts: Any, citations: list[str]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "question": question,
        "supported": True,
        "intent": intent,
        "answer": answer,
        "facts": facts,
        "citations": citations,
        "authority": "deterministic_service",
        "agent_scope": "local_llm_may_narrate_tool_facts_only",
    }


def _unsupported(question: str, run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "question": question,
        "supported": False,
        "intent": "unsupported",
        "answer": "The gas risk pack query tool does not support that question from the current materialized pack.",
        "facts": {},
        "citations": [],
        "authority": "deterministic_service",
        "agent_scope": "local_llm_must_not_invent_missing_facts",
        "exception": {"code": GAS_RISK_QUERY_UNSUPPORTED, "blocking": True},
    }


def _date_in_question(question: str) -> str | None:
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", question)
    return None if match is None else match.group(1)
