from __future__ import annotations

import re
from typing import Any

from ..exceptions import WorkbenchException
from ..serialization import to_plain
from .normalization import normalize_positions
from .pnl import run_pnl_attribution
from .ports import BuiltinBlack76PricingPort, PricingPort

GAS_PORTFOLIO_QUERY_UNSUPPORTED = "GAS_PORTFOLIO_QUERY_UNSUPPORTED"

CONTRACT_SIZE_MMBTU = 2500.0


def _linear_position_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "2026-06-01": [
            _linear_row("2026-06-01", "HH-FUT-N26", "H", "N26", 4, 3.10, "Gas Delta", "outright", "core", "prompt", "hedge,hh"),
            _linear_row("2026-06-01", "HH-FUT-Q26", "H", "Q326", -2, 3.25, "Gas Delta", "calendar", "core", "summer", "short,hh"),
        ],
        "2026-06-02": [
            _linear_row("2026-06-02", "HH-FUT-N26", "H", "N26", 4, 3.20, "Gas Delta", "outright", "core", "prompt", "hedge,hh"),
            _linear_row("2026-06-02", "HH-FUT-Q26", "H", "Q326", -2, 3.18, "Gas Delta", "calendar", "core", "summer", "short,hh"),
        ],
        "2026-06-03": [
            _linear_row("2026-06-03", "HH-FUT-N26", "H", "N26", 2, 3.05, "Gas Delta", "outright", "core", "prompt", "hedge,hh,partial-close"),
            _linear_row("2026-06-03", "HH-FUT-Q26", "H", "Q326", -2, 3.05, "Gas Delta", "calendar", "core", "summer", "short,hh"),
        ],
    }


def _linear_row(
    as_of_date: str,
    position_id: str,
    raw_product: str,
    raw_period: str,
    contracts: float,
    mark: float,
    book: str,
    strategy: str,
    portfolio: str,
    sleeve: str,
    tags: str,
) -> dict[str, Any]:
    return {
        "as_of": f"{as_of_date}T12:00:00Z",
        "position_id": position_id,
        "raw_product": raw_product,
        "raw_period": raw_period,
        "raw_quantity": contracts,
        "quantity_unit": "contracts",
        "delivery_days": 31,
        "raw_mark": mark,
        "book": book,
        "strategy": strategy,
        "portfolio": portfolio,
        "sleeve": sleeve,
        "tags": tags,
        "metadata": {"sample_portfolio": True, "synthetic": True},
        "source": "synthetic_gas_portfolio_fixture",
        "source_role": "synthetic_test_fixture",
    }


def _option_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "2026-06-01": [
            _option_row("2026-06-01", "PHE-C-3.25-N26", "call", 3, 3.10, 3.25, 0.45, 0.120, "Gas Options", "vol", "core", "prompt"),
            _option_row("2026-06-01", "PHE-P-3.00-Q326", "put", -2, 3.25, 3.00, 0.40, 0.165, "Gas Options", "vol", "core", "summer"),
        ],
        "2026-06-02": [
            _option_row("2026-06-02", "PHE-C-3.25-N26", "call", 3, 3.20, 3.25, 0.43, 0.117, "Gas Options", "vol", "core", "prompt"),
            _option_row("2026-06-02", "PHE-P-3.00-Q326", "put", -2, 3.18, 3.00, 0.39, 0.162, "Gas Options", "vol", "core", "summer"),
        ],
        "2026-06-03": [
            _option_row("2026-06-03", "PHE-C-3.25-N26", "call", 3, 3.05, 3.25, 0.48, 0.114, "Gas Options", "vol", "core", "prompt"),
            _option_row("2026-06-03", "PHE-P-3.00-Q326", "put", -1, 3.05, 3.00, 0.42, 0.159, "Gas Options", "vol", "core", "summer"),
        ],
    }


def _option_row(
    as_of_date: str,
    option_id: str,
    option_type: str,
    position: float,
    forward: float,
    strike: float,
    volatility: float,
    time_to_expiry_years: float,
    book: str,
    strategy: str,
    portfolio: str,
    sleeve: str,
) -> dict[str, Any]:
    return {
        "as_of": f"{as_of_date}T12:00:00Z",
        "option_symbol": "PHE",
        "option_id": option_id,
        "delivery_period_id": "N26" if "N26" in option_id else "Q326",
        "option_type": option_type,
        "position": position,
        "forward": forward,
        "strike": strike,
        "volatility": volatility,
        "time_to_expiry_years": time_to_expiry_years,
        "book": book,
        "strategy": strategy,
        "portfolio": portfolio,
        "sleeve": sleeve,
        "tags": ["option", "phe", "hh"],
        "source": "synthetic_gas_portfolio_fixture",
        "source_role": "synthetic_test_fixture",
    }


def build_sample_gas_portfolio_report(run_id: str = "gas-portfolio-sample", pricing_port: PricingPort | None = None) -> dict[str, Any]:
    pricing_port = pricing_port or BuiltinBlack76PricingPort()
    linear_rows = _linear_position_rows()
    option_rows = _option_rows()
    as_of_dates = sorted(linear_rows)

    normalized_by_date = {as_of: normalize_positions(rows) for as_of, rows in linear_rows.items()}
    option_valuations_by_date = {as_of: _option_valuations(option_rows[as_of], pricing_port) for as_of in as_of_dates}
    summaries = []
    pnl_periods = []

    prior_total_value: float | None = None
    cumulative_total_pnl = 0.0
    for as_of in as_of_dates:
        linear_value = sum(float(position.derived["market_value"]) for position in normalized_by_date[as_of])
        option_value = sum(float(row["market_value"]) for row in option_valuations_by_date[as_of])
        total_value = linear_value + option_value
        daily_total_pnl = None if prior_total_value is None else total_value - prior_total_value
        if daily_total_pnl is not None:
            cumulative_total_pnl += daily_total_pnl
        summaries.append(
            {
                "as_of": as_of,
                "linear_market_value": linear_value,
                "option_market_value": option_value,
                "total_market_value": total_value,
                "daily_total_pnl": daily_total_pnl,
                "cumulative_total_pnl": cumulative_total_pnl,
                "net_option_delta": sum(float(row["position_delta"]) for row in option_valuations_by_date[as_of]),
                "net_option_vega": sum(float(row["position_vega"]) for row in option_valuations_by_date[as_of]),
            }
        )
        prior_total_value = total_value

    for prior_as_of, current_as_of in zip(as_of_dates, as_of_dates[1:]):
        linear_pnl = run_pnl_attribution(
            normalized_by_date[prior_as_of],
            normalized_by_date[current_as_of],
            run_id=f"{run_id}-{prior_as_of}-to-{current_as_of}-linear-pnl",
        )
        option_pnl = _option_pnl(option_valuations_by_date[prior_as_of], option_valuations_by_date[current_as_of])
        total_option_pnl = sum(float(row["pnl"]) for row in option_pnl)
        total_pnl = float(linear_pnl.independent_total_effect) + total_option_pnl
        pnl_periods.append(
            {
                "prior_as_of": prior_as_of,
                "current_as_of": current_as_of,
                "linear_pnl": to_plain(linear_pnl),
                "option_pnl": option_pnl,
                "total_option_pnl": total_option_pnl,
                "total_pnl": total_pnl,
                "book_pnl": _book_pnl(linear_pnl.group_breakdowns, option_pnl),
            }
        )

    return {
        "run_id": run_id,
        "scenario_id": "synthetic_hh_gas_portfolio_through_time",
        "synthetic": True,
        "source_role": "synthetic_test_fixture",
        "authority": "deterministic_service",
        "model_scope": {
            "linear_positions": "deterministic_mark_to_market",
            "options": "Black76_screening_analytics_on_registered_ICE_PHE",
            "agent": "non_authoritative_narration_only",
        },
        "as_of_dates": as_of_dates,
        "linear_positions_by_as_of": {as_of: to_plain(positions) for as_of, positions in normalized_by_date.items()},
        "option_positions_by_as_of": option_valuations_by_date,
        "summaries": summaries,
        "pnl_periods": pnl_periods,
        "local_llm_test": {
            "tool_command": "artemis analyst gas-portfolio query --input REPORT --question QUESTION --output ANSWER",
            "allowed_scope": "retrieve, summarize, and explain deterministic report facts",
            "forbidden_scope": "recalculate unsupported analytics, mutate state, promote synthetic data, or invent missing facts",
            "starter_questions": [
                "What was total PnL through time?",
                "What positions did we have on 2026-06-03?",
                "What was Gas Options book PnL?",
                "What were the latest option Greeks?",
            ],
        },
        "lineage": {
            "records": [
                "src/pga_workbench/services/gas_portfolio.py",
                "src/pga_workbench/services/ports.py",
                "src/pga_workbench/services/normalization.py",
                "src/pga_workbench/services/pnl.py",
                "src/pga_workbench/services/greeks.py",
            ],
            "ports": {
                "pricing": {
                    "port_id": pricing_port.port_id,
                    "implementation": pricing_port.implementation,
                }
            },
            "non_authority_notes": ["Synthetic data is local-test only and must not publish to authoritative shared cache."],
        },
    }


def _option_valuations(rows: list[dict[str, Any]], pricing_port: PricingPort) -> list[dict[str, Any]]:
    greeks = pricing_port.option_greeks(rows, run_id="gas-portfolio-option-greeks")
    by_id = {str(row["option_id"]): row for row in rows}
    valued = []
    for greek in greeks.greeks:
        source = by_id[str(greek["option_id"])]
        position = float(source["position"])
        model_price = float(greek["model_price"])
        valued.append(
            {
                **{key: source[key] for key in ["as_of", "option_id", "book", "strategy", "portfolio", "sleeve", "tags", "source", "source_role"]},
                "option_contract_id": greek["option_contract_id"],
                "underlying_index_id": greek["underlying_index_id"],
                "delivery_period_id": greek["delivery_period_id"],
                "option_type": greek["option_type"],
                "position": position,
                "forward": greek["forward"],
                "strike": greek["strike"],
                "volatility": greek["volatility"],
                "time_to_expiry_years": greek["time_to_expiry_years"],
                "contract_size_mmbtu": CONTRACT_SIZE_MMBTU,
                "model_price": model_price,
                "market_value": model_price * position * CONTRACT_SIZE_MMBTU,
                "position_delta": greek["position_delta"],
                "position_gamma": greek["position_gamma"],
                "position_vega": greek["position_vega"],
                "position_theta": greek["position_theta"],
                "analytics_scope": greek["analytics_scope"],
                "vol_input_scope": greek["vol_input_scope"],
                "model_scope": greek["model_scope"],
            }
        )
    return valued


def _option_pnl(prior: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prior_by_id = {str(row["option_id"]): row for row in prior}
    current_by_id = {str(row["option_id"]): row for row in current}
    rows = []
    for option_id in sorted(set(prior_by_id) | set(current_by_id)):
        p0 = prior_by_id.get(option_id)
        p1 = current_by_id.get(option_id)
        prior_value = float(p0["market_value"]) if p0 else 0.0
        current_value = float(p1["market_value"]) if p1 else 0.0
        source = p1 or p0 or {}
        rows.append(
            {
                "option_id": option_id,
                "book": source.get("book"),
                "strategy": source.get("strategy"),
                "portfolio": source.get("portfolio"),
                "sleeve": source.get("sleeve"),
                "prior_market_value": prior_value,
                "current_market_value": current_value,
                "pnl": current_value - prior_value,
                "model_scope": source.get("model_scope"),
            }
        )
    return rows


def _book_pnl(linear_group_breakdowns: list[dict[str, Any]], option_pnl: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, float] = {}
    for item in linear_group_breakdowns:
        if item.get("dimension") == "book":
            totals[str(item["value"])] = totals.get(str(item["value"]), 0.0) + float(item["total_effect"])
    for item in option_pnl:
        book = item.get("book")
        if book:
            totals[str(book)] = totals.get(str(book), 0.0) + float(item["pnl"])
    return [{"book": book, "pnl": pnl} for book, pnl in sorted(totals.items())]


def query_gas_portfolio_report(report: dict[str, Any], question: str, run_id: str = "gas-portfolio-query") -> dict[str, Any]:
    q = question.strip()
    lowered = q.lower()
    if not q:
        raise WorkbenchException(GAS_PORTFOLIO_QUERY_UNSUPPORTED, "Question is required")
    if any(term in lowered for term in ["total pnl", "pnl through time", "cumulative pnl"]):
        return _answer_total_pnl(report, q, run_id)
    if "position" in lowered or "positions" in lowered:
        return _answer_positions(report, q, run_id)
    if "book" in lowered and "pnl" in lowered:
        return _answer_book_pnl(report, q, run_id)
    if any(term in lowered for term in ["greek", "delta", "vega", "gamma", "theta"]):
        return _answer_greeks(report, q, run_id)
    return _unsupported(q, run_id)


def _answer_total_pnl(report: dict[str, Any], question: str, run_id: str) -> dict[str, Any]:
    facts = [
        {
            "period": f"{period['prior_as_of']} to {period['current_as_of']}",
            "linear_pnl": period["linear_pnl"]["independent_total_effect"],
            "option_pnl": period["total_option_pnl"],
            "total_pnl": period["total_pnl"],
        }
        for period in report["pnl_periods"]
    ]
    total = sum(float(item["total_pnl"]) for item in facts)
    answer = f"Total PnL across the sample window was {total:.2f} USD."
    return _supported(question, run_id, "total_pnl", answer, facts, ["pnl_periods"])


def _answer_positions(report: dict[str, Any], question: str, run_id: str) -> dict[str, Any]:
    as_of = _date_in_question(question) or report["as_of_dates"][-1]
    if as_of not in report["linear_positions_by_as_of"]:
        return _unsupported(question, run_id, reason=f"No sample portfolio date found for {as_of}")
    linear = [
        {
            "position_id": row["position_id"],
            "instrument_id": row["position_lot"]["instrument_id"],
            "signed_quantity": row["position_lot"]["signed_quantity"],
            "quantity_unit": row["position_lot"]["quantity_unit"],
            "market_value": row["derived"]["market_value"],
            "book": row["identity"]["book"],
            "strategy": row["identity"]["strategy"],
        }
        for row in report["linear_positions_by_as_of"][as_of]
    ]
    options = [
        {
            "option_id": row["option_id"],
            "option_type": row["option_type"],
            "position": row["position"],
            "market_value": row["market_value"],
            "book": row["book"],
            "strategy": row["strategy"],
        }
        for row in report["option_positions_by_as_of"][as_of]
    ]
    answer = f"On {as_of}, the sample held {len(linear)} linear gas positions and {len(options)} PHE option positions."
    return _supported(question, run_id, "positions_by_date", answer, {"as_of": as_of, "linear": linear, "options": options}, ["linear_positions_by_as_of", "option_positions_by_as_of"])


def _answer_book_pnl(report: dict[str, Any], question: str, run_id: str) -> dict[str, Any]:
    totals: dict[str, float] = {}
    for period in report["pnl_periods"]:
        for item in period["book_pnl"]:
            totals[str(item["book"])] = totals.get(str(item["book"]), 0.0) + float(item["pnl"])
    facts = [{"book": book, "pnl": pnl} for book, pnl in sorted(totals.items())]
    answer = "Book PnL was " + ", ".join(f"{item['book']}: {item['pnl']:.2f} USD" for item in facts) + "."
    return _supported(question, run_id, "book_pnl", answer, facts, ["pnl_periods.book_pnl"])


def _answer_greeks(report: dict[str, Any], question: str, run_id: str) -> dict[str, Any]:
    as_of = _date_in_question(question) or report["as_of_dates"][-1]
    if as_of not in report["option_positions_by_as_of"]:
        return _unsupported(question, run_id, reason=f"No sample option date found for {as_of}")
    rows = report["option_positions_by_as_of"][as_of]
    facts = {
        "as_of": as_of,
        "net_delta": sum(float(row["position_delta"]) for row in rows),
        "net_gamma": sum(float(row["position_gamma"]) for row in rows),
        "net_vega": sum(float(row["position_vega"]) for row in rows),
        "net_theta": sum(float(row["position_theta"]) for row in rows),
        "rows": [
            {
                "option_id": row["option_id"],
                "position_delta": row["position_delta"],
                "position_gamma": row["position_gamma"],
                "position_vega": row["position_vega"],
                "position_theta": row["position_theta"],
                "analytics_scope": row["analytics_scope"],
            }
            for row in rows
        ],
    }
    answer = f"On {as_of}, net option delta was {facts['net_delta']:.6f} and net option vega was {facts['net_vega']:.6f}; Greeks are screening-only Black-76 outputs."
    return _supported(question, run_id, "option_greeks", answer, facts, ["option_positions_by_as_of"])


def _date_in_question(question: str) -> str | None:
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", question)
    return None if match is None else match.group(1)


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


def _unsupported(question: str, run_id: str, reason: str | None = None) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "question": question,
        "supported": False,
        "intent": "unsupported",
        "answer": reason or "The gas portfolio query tool does not support that question from the current deterministic report.",
        "facts": {},
        "citations": [],
        "authority": "deterministic_service",
        "agent_scope": "local_llm_must_not_invent_missing_facts",
        "exception": {
            "code": GAS_PORTFOLIO_QUERY_UNSUPPORTED,
            "blocking": True,
        },
    }
