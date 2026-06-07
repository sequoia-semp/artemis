from __future__ import annotations

from pathlib import Path

from pga_workbench.cli import artemis_main, main
from pga_workbench.registry import validate_registries
from pga_workbench.serialization import read_json
from pga_workbench.services.gas_integration import (
    build_gas_contract_definition_catalog,
    build_gas_daily_risk_history,
    build_gas_integration_bundle,
    build_gas_risk_oracle,
    build_portfolio_rollup_reconciliation,
)
from pga_workbench.services.gas_portfolio import build_sample_gas_portfolio_report


ROOT = Path(__file__).resolve().parents[1]


def test_gas_contract_definition_catalog_uses_registry_definitions():
    catalog = build_gas_contract_definition_catalog(ROOT / "registries")

    future_ids = {row["contract_id"] for row in catalog["futures"]}
    option_ids = {row["contract_id"] for row in catalog["options"]}
    assert "ICE_H_HENRY_LD1_FIXED_PRICE_FUTURE" in future_ids
    assert "ICE_PHE_OPTION_HENRY_PENULTIMATE_FIXED_PRICE" in option_ids
    assert catalog["quantity_conventions"]["ICE_GAS_CONTRACT_0_25D_EQUIVALENT"]["mmbtu_per_contract_per_day"] == 2500
    assert catalog["authority"] == "registry_derived"


def test_gas_portfolio_rollup_reconciliation_covers_standard_dimensions():
    report = build_sample_gas_portfolio_report()
    rollups = build_portfolio_rollup_reconciliation(report)

    assert rollups["all_reconciled"] is True
    latest = rollups["market_value_rollups"][-1]
    assert set(latest["dimensions"]) == {"book", "strategy", "portfolio", "sleeve", "tag"}
    assert latest["checks"]["book"]["passed"] is True
    assert latest["checks"]["strategy"]["passed"] is True
    assert latest["checks"]["tag"]["checked"] is False

    pnl = rollups["pnl_rollups"][-1]
    assert pnl["checks"]["book"]["passed"] is True
    assert pnl["checks"]["strategy"]["passed"] is True


def test_gas_daily_risk_history_and_oracle_are_materialized(tmp_path: Path):
    report = build_sample_gas_portfolio_report()
    history = build_gas_daily_risk_history(report, tmp_path, force=True)
    oracle = build_gas_risk_oracle(report, tmp_path)

    assert [row["as_of"] for row in history["rows"]] == report["as_of_dates"]
    assert history["query_index"]["latest"]["as_of"] == "2026-06-03"
    assert history["query_index"]["var_95_series"]
    assert oracle["all_passed"] is True
    assert {check["check_id"] for check in oracle["checks"]} == {"parallel_down_20c_handcalc", "option_explain_totals_bridge"}


def test_gas_integration_bundle_proves_success_criteria(tmp_path: Path):
    bundle = build_gas_integration_bundle(tmp_path, registry_dir=ROOT / "registries", force=True)

    assert bundle["bundle_version"] == "gas_integration_bundle_v0.1"
    assert bundle["success_criteria"] == {
        "rollups_reconciled": True,
        "risk_oracle_passed": True,
        "narrative_grounded": True,
        "shared_cache_unchanged": True,
    }
    assert bundle["diagnostics"]["gates"]["strategy_label_authority"] == "advisory_reporting_metadata_only"
    assert bundle["contract_definitions"]["options"]


def test_gas_integration_cli_and_tool_registry_validate(tmp_path: Path):
    output = tmp_path / "gas_integration_bundle.json"

    assert (
        artemis_main(
            [
                "analyst",
                "gas-integration",
                "build",
                "--output",
                str(output),
                "--output-root",
                str(tmp_path / "risk-cache"),
                "--registries",
                str(ROOT / "registries"),
                "--force",
            ]
        )
        == 0
    )
    assert read_json(output)["success_criteria"]["risk_oracle_passed"] is True

    pga_output = tmp_path / "pga_gas_integration_bundle.json"
    assert main(["build-gas-integration-bundle", "--output", str(pga_output), "--output-root", str(tmp_path / "pga-risk-cache"), "--registries", str(ROOT / "registries")]) == 0
    assert read_json(pga_output)["success_criteria"]["rollups_reconciled"] is True

    registry_result = validate_registries(ROOT / "registries", ROOT / "schemas")
    assert "tools.yaml" in registry_result.validated_files
