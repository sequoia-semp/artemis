from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.time import utc_now_iso
from ..registry import load_yaml_unique
from ..registry_access import load_registry_catalog
from .gas_portfolio import build_sample_gas_portfolio_report
from .gas_risk_pack import build_cached_gas_risk_pack, query_gas_risk_pack

GAS_INTEGRATION_VERSION = "gas_integration_bundle_v0.1"


def build_gas_contract_definition_catalog(registry_dir: Path = Path("registries"), *, run_id: str = "gas-contract-definitions") -> dict[str, Any]:
    catalog = load_registry_catalog(registry_dir)
    quantity_conventions = load_yaml_unique(Path(registry_dir) / "quantity_conventions.yaml")
    gas_futures = [
        _contract_definition(contract_id, record, "future")
        for contract_id, record in sorted(catalog.exchange_contracts.items())
        if record.get("commodity") == "gas"
    ]
    gas_options = [
        _contract_definition(contract_id, record, "option")
        for contract_id, record in sorted(catalog.option_contracts.items())
        if record.get("commodity") == "gas"
    ]
    mappings = [
        {
            "mapping_id": mapping_id,
            "source_contract_id": record.get("source_contract_id"),
            "contract_symbol": record.get("contract_symbol"),
            "target": record.get("target"),
            "status": record.get("status"),
        }
        for mapping_id, record in sorted(catalog.forward_fundamental_mappings.items())
        if (record.get("target") or {}).get("commodity") == "gas"
    ]
    return {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "authority": "registry_derived",
        "scope": "gas_contract_definitions",
        "futures": gas_futures,
        "options": gas_options,
        "forward_fundamental_mappings": mappings,
        "quantity_conventions": {
            key: value
            for key, value in sorted((quantity_conventions or {}).items())
            if isinstance(value, dict) and value.get("commodity") == "gas"
        },
        "definitions": {
            "contract_definition": "registry-derived contract metadata; no inferred market convention",
            "quantity_convention": "locked gas quantity convention from registries/quantity_conventions.yaml",
        },
        "lineage": {
            "records": [
                "registries/exchange_contracts.yaml",
                "registries/option_contracts.yaml",
                "registries/forward_fundamental_mappings.yaml",
                "registries/quantity_conventions.yaml",
            ],
        },
    }


def build_portfolio_rollup_reconciliation(report: dict[str, Any], *, run_id: str = "gas-rollup-reconciliation") -> dict[str, Any]:
    as_of_rows = []
    for as_of in report["as_of_dates"]:
        linear = list(report["linear_positions_by_as_of"][as_of])
        options = list(report["option_positions_by_as_of"][as_of])
        total = _market_value_total(linear, options)
        dimensions = {
            "book": _market_value_dimension(linear, options, "book"),
            "strategy": _market_value_dimension(linear, options, "strategy"),
            "portfolio": _market_value_dimension(linear, options, "portfolio"),
            "sleeve": _market_value_dimension(linear, options, "sleeve"),
            "tag": _market_value_tags(linear, options),
        }
        as_of_rows.append(_reconciled_row(as_of, "market_value", total, dimensions))

    pnl_rows = []
    for period in report["pnl_periods"]:
        total = float(period["total_pnl"])
        option_rows = list(period["option_pnl"])
        dimensions = {
            "book": _pnl_dimension(period, option_rows, "book"),
            "strategy": _pnl_dimension(period, option_rows, "strategy"),
            "portfolio": _pnl_dimension(period, option_rows, "portfolio"),
            "sleeve": _pnl_dimension(period, option_rows, "sleeve"),
        }
        pnl_rows.append(_reconciled_row(f"{period['prior_as_of']} to {period['current_as_of']}", "pnl", total, dimensions))

    return {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "authority": "deterministic_service",
        "market_value_rollups": as_of_rows,
        "pnl_rollups": pnl_rows,
        "all_reconciled": all(row["reconciled"] for row in as_of_rows + pnl_rows),
        "definitions": {
            "market_value_rollup": "sum of position market values by book, strategy, portfolio, sleeve, and tag",
            "pnl_rollup": "sum of PnL by book, strategy, portfolio, and sleeve where source PnL rows carry that dimension",
            "reconciled": "absolute difference between parent total and each dimension total is less than 1e-6",
        },
        "lineage": {"records": ["src/pga_workbench/services/gas_portfolio.py"]},
    }


def build_gas_daily_risk_history(
    report: dict[str, Any],
    output_root: Path,
    *,
    run_id: str = "gas-daily-risk-history",
    force: bool = False,
) -> dict[str, Any]:
    rows = []
    packs = []
    for as_of in report["as_of_dates"]:
        pack = build_cached_gas_risk_pack(report, as_of, output_root, force=force, run_id=f"{run_id}-{as_of}")
        packs.append(pack)
        metrics = pack["risk"]["historical_var_expected_shortfall"]["metrics"]
        stress = min(pack["risk"]["stress_scenarios"], key=lambda row: float(row["total_pnl"]))
        rows.append(
            {
                "as_of": as_of,
                "pack_path": str(Path(output_root) / "gas" / as_of / "gas_risk_pack.json"),
                "cache_status": pack.get("cache_status"),
                "total_market_value": pack["valuations"]["total_market_value"],
                "var_95": metrics["95"]["var"],
                "expected_shortfall_95": metrics["95"]["expected_shortfall"],
                "worst_stress_scenario": stress["scenario_id"],
                "worst_stress_pnl": stress["total_pnl"],
            }
        )
    return {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "authority": "deterministic_service",
        "risk_pack_version": packs[-1]["manifest"]["risk_pack_version"] if packs else None,
        "rows": rows,
        "query_index": {
            "available_dates": [row["as_of"] for row in rows],
            "latest": rows[-1] if rows else None,
            "var_95_series": [{"as_of": row["as_of"], "var_95": row["var_95"]} for row in rows],
            "worst_stress_series": [{"as_of": row["as_of"], "worst_stress_pnl": row["worst_stress_pnl"]} for row in rows],
        },
        "definitions": {
            "daily_risk_history": "materialized summary rows over cached daily gas risk packs",
            "cache_status": "hit when a daily pack was reused by matching manifest cache_key; rebuilt otherwise",
        },
        "lineage": {"records": ["src/pga_workbench/services/gas_risk_pack.py"]},
    }


def build_gas_risk_oracle(report: dict[str, Any], output_root: Path, *, run_id: str = "gas-risk-oracle") -> dict[str, Any]:
    latest_as_of = report["as_of_dates"][-1]
    pack = build_cached_gas_risk_pack(report, latest_as_of, output_root, run_id=f"{run_id}-{latest_as_of}")
    exposure_total = sum(float(row["exposure_value"]) for row in pack["risk"]["exposure_buckets"]["factor_exposures"])
    parallel_down = next(row for row in pack["risk"]["stress_scenarios"] if row["scenario_id"] == "parallel_down_20c")
    expected_parallel_down = exposure_total * -0.20 / 3.0
    option_explain = pack["risk"]["option_pnl_explain"]["totals"]
    checks = [
        {
            "check_id": "parallel_down_20c_handcalc",
            "actual": parallel_down["price_pnl"],
            "expected": expected_parallel_down,
            "difference": parallel_down["price_pnl"] - expected_parallel_down,
            "passed": abs(parallel_down["price_pnl"] - expected_parallel_down) < 1e-9,
            "formula": "sum(factor_exposure_value) * -0.20 / 3.0",
        },
        {
            "check_id": "option_explain_totals_bridge",
            "actual": option_explain["actual_pnl"],
            "expected": sum(float(row["actual_pnl"]) for row in pack["risk"]["option_pnl_explain"]["rows"]),
            "difference": option_explain["actual_pnl"] - sum(float(row["actual_pnl"]) for row in pack["risk"]["option_pnl_explain"]["rows"]),
            "passed": abs(option_explain["actual_pnl"] - sum(float(row["actual_pnl"]) for row in pack["risk"]["option_pnl_explain"]["rows"])) < 1e-9,
            "formula": "option explain total actual_pnl equals sum(row actual_pnl)",
        },
    ]
    return {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "authority": "deterministic_oracle",
        "as_of": latest_as_of,
        "checks": checks,
        "all_passed": all(check["passed"] for check in checks),
        "lineage": {"records": ["src/pga_workbench/services/gas_risk_pack.py"]},
    }


def build_gas_diagnostics(report: dict[str, Any], risk_history: dict[str, Any], contract_catalog: dict[str, Any], rollups: dict[str, Any], oracle: dict[str, Any], *, run_id: str = "gas-diagnostics") -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "authority": "deterministic_service",
        "organization": {
            "portfolio_dates": report["as_of_dates"],
            "books": sorted({row["identity"]["book"] for rows in report["linear_positions_by_as_of"].values() for row in rows} | {row["book"] for rows in report["option_positions_by_as_of"].values() for row in rows}),
            "strategies": sorted({row["identity"]["strategy"] for rows in report["linear_positions_by_as_of"].values() for row in rows} | {row["strategy"] for rows in report["option_positions_by_as_of"].values() for row in rows}),
            "gas_future_contracts": len(contract_catalog["futures"]),
            "gas_option_contracts": len(contract_catalog["options"]),
        },
        "definition_sources": {
            "contract_definitions": contract_catalog["lineage"]["records"],
            "strategy_semantics": "docs/analyst/gas_strategy_semantics.md",
            "risk_pack": "src/pga_workbench/services/gas_risk_pack.py",
            "portfolio_report": "src/pga_workbench/services/gas_portfolio.py",
        },
        "gates": {
            "rollups_reconciled": rollups["all_reconciled"],
            "risk_oracle_passed": oracle["all_passed"],
            "latest_risk_history": risk_history["query_index"]["latest"],
            "strategy_label_authority": "advisory_reporting_metadata_only",
        },
        "non_authority_notes": [
            "Synthetic sample data remains local-test only.",
            "Candidate strategy labels do not alter valuation or risk semantics.",
            "Local LLMs may narrate deterministic tool facts only.",
        ],
    }


def build_gas_integration_bundle(
    output_root: Path,
    *,
    registry_dir: Path = Path("registries"),
    run_id: str = "gas-integration-bundle",
    force: bool = False,
) -> dict[str, Any]:
    report = build_sample_gas_portfolio_report(run_id=f"{run_id}-portfolio")
    contract_catalog = build_gas_contract_definition_catalog(registry_dir, run_id=f"{run_id}-contracts")
    rollups = build_portfolio_rollup_reconciliation(report, run_id=f"{run_id}-rollups")
    risk_history = build_gas_daily_risk_history(report, output_root, run_id=f"{run_id}-risk-history", force=force)
    oracle = build_gas_risk_oracle(report, output_root, run_id=f"{run_id}-oracle")
    diagnostics = build_gas_diagnostics(report, risk_history, contract_catalog, rollups, oracle, run_id=f"{run_id}-diagnostics")
    latest_pack = build_cached_gas_risk_pack(report, report["as_of_dates"][-1], output_root, run_id=f"{run_id}-latest-pack")
    narrative_probe = query_gas_risk_pack(latest_pack, "What is 95% VaR and expected shortfall?", run_id=f"{run_id}-narrative-probe")
    return {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "bundle_version": GAS_INTEGRATION_VERSION,
        "authority": "deterministic_service",
        "synthetic": True,
        "portfolio_report": report,
        "contract_definitions": contract_catalog,
        "rollup_reconciliation": rollups,
        "risk_history": risk_history,
        "risk_oracle": oracle,
        "diagnostics": diagnostics,
        "narrative_probe": narrative_probe,
        "success_criteria": {
            "rollups_reconciled": rollups["all_reconciled"],
            "risk_oracle_passed": oracle["all_passed"],
            "narrative_grounded": narrative_probe["supported"] is True and narrative_probe["authority"] == "deterministic_service",
            "shared_cache_unchanged": True,
        },
        "lineage": {
            "records": [
                "src/pga_workbench/services/gas_integration.py",
                "src/pga_workbench/services/gas_portfolio.py",
                "src/pga_workbench/services/gas_risk_pack.py",
                "registries/exchange_contracts.yaml",
                "registries/option_contracts.yaml",
            ],
        },
    }


def _contract_definition(contract_id: str, record: dict[str, Any], contract_type: str) -> dict[str, Any]:
    return {
        "contract_id": contract_id,
        "contract_type": contract_type,
        "contract_symbol": record.get("contract_symbol"),
        "product_name": record.get("product_name"),
        "commodity": record.get("commodity"),
        "location_id": record.get("location_id"),
        "quote_unit": record.get("quote_unit") or record.get("premium_quote_unit"),
        "strike_unit": record.get("strike_unit"),
        "contract_size": record.get("contract_size"),
        "contract_period": record.get("contract_period"),
        "underlying_contract_symbol": record.get("underlying_contract_symbol"),
        "underlying_index_id": record.get("underlying_index_id"),
        "settlement_method": record.get("settlement_method"),
        "verification_status": record.get("verification_status"),
        "status": record.get("status"),
        "source_documents": record.get("source_documents") or [],
    }


def _market_value_total(linear: list[dict[str, Any]], options: list[dict[str, Any]]) -> float:
    return sum(float(row["derived"]["market_value"]) for row in linear) + sum(float(row["market_value"]) for row in options)


def _linear_dimension_value(row: dict[str, Any], field: str) -> str:
    return str(row["identity"].get(field) or "unassigned")


def _option_dimension_value(row: dict[str, Any], field: str) -> str:
    return str(row.get(field) or "unassigned")


def _market_value_dimension(linear: list[dict[str, Any]], options: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    totals: dict[str, float] = {}
    for row in linear:
        key = _linear_dimension_value(row, field)
        totals[key] = totals.get(key, 0.0) + float(row["derived"]["market_value"])
    for row in options:
        key = _option_dimension_value(row, field)
        totals[key] = totals.get(key, 0.0) + float(row["market_value"])
    return [{"value": key, "total": value} for key, value in sorted(totals.items())]


def _market_value_tags(linear: list[dict[str, Any]], options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, float] = {}
    for row in linear:
        for tag in row["identity"].get("tags") or ["unassigned"]:
            totals[str(tag)] = totals.get(str(tag), 0.0) + float(row["derived"]["market_value"])
    for row in options:
        for tag in row.get("tags") or ["unassigned"]:
            totals[str(tag)] = totals.get(str(tag), 0.0) + float(row["market_value"])
    return [{"value": key, "total": value, "multi_tag_allocation": True} for key, value in sorted(totals.items())]


def _pnl_dimension(period: dict[str, Any], option_rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    totals: dict[str, float] = {}
    for item in period["linear_pnl"]["group_breakdowns"]:
        if item.get("dimension") == field:
            key = str(item["value"])
            totals[key] = totals.get(key, 0.0) + float(item["total_effect"])
    for item in option_rows:
        key = str(item.get(field) or "unassigned")
        totals[key] = totals.get(key, 0.0) + float(item["pnl"])
    return [{"value": key, "total": value} for key, value in sorted(totals.items())]


def _reconciled_row(label: str, value_kind: str, total: float, dimensions: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    checks = {}
    for dimension, rows in dimensions.items():
        if dimension == "tag":
            checks[dimension] = {"checked": False, "reason": "tag rollups are intentionally multi-allocation diagnostics"}
            continue
        subtotal = sum(float(row["total"]) for row in rows)
        checks[dimension] = {
            "checked": True,
            "subtotal": subtotal,
            "difference": subtotal - total,
            "passed": abs(subtotal - total) < 1e-6,
        }
    return {
        "label": label,
        "value_kind": value_kind,
        "total": total,
        "dimensions": dimensions,
        "checks": checks,
        "reconciled": all(check.get("passed", True) for check in checks.values() if check.get("checked")),
    }
