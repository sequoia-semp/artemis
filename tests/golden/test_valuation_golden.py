from __future__ import annotations

import json
from pathlib import Path

import pytest

from pga_workbench.exceptions import VALUATION_INSUFFICIENT_DATA, WorkbenchException
from pga_workbench.exceptions import VALUATION_TIE_OUT_FAILED
from pga_workbench.services.greeks import run_black76_greeks
from pga_workbench.models import RiskFactorId
from pga_workbench.services.normalization import normalize_positions
from pga_workbench.services import pnl as pnl_service
from pga_workbench.services.pnl import run_pnl_attribution
from pga_workbench.services.risk import run_historical_var


SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


def _scenario(name: str) -> dict:
    return json.loads((SCENARIO_DIR / name).read_text(encoding="utf-8"))


def _assert_float_map(actual: dict, expected: dict, *, abs_tol: float) -> None:
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if isinstance(expected_value, bool):
            assert actual_value is expected_value
        else:
            assert actual_value == pytest.approx(expected_value, abs=abs_tol)


@pytest.mark.parametrize("scenario_path", sorted(SCENARIO_DIR.glob("*.json")))
def test_golden_valuation_scenarios(scenario_path: Path):
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    abs_tol = float(scenario["tolerances"]["absolute"])
    greeks_abs_tol = float(scenario["tolerances"]["greeks_absolute"])

    if "pnl" in scenario:
        pnl = scenario["pnl"]
        pnl_report = run_pnl_attribution(
            normalize_positions(pnl["prior_positions"]),
            normalize_positions(pnl["current_positions"]),
            run_id=scenario["scenario_id"],
        )
        _assert_float_map(
            {
                "price_move_effect": pnl_report.price_move_effect,
                "position_change_effect": pnl_report.position_change_effect,
                "basis_move_effect": pnl_report.basis_move_effect,
                "strip_weight_effect": pnl_report.strip_weight_effect,
                "atc_component_effect": pnl_report.atc_component_effect,
                "mark_adjustment_effect": pnl_report.mark_adjustment_effect,
                "unexplained_residual": pnl_report.unexplained_residual,
                "bridge_sums": pnl_report.bridge_sums,
                "independent_total_effect": pnl_report.independent_total_effect,
                "explained_total_effect": pnl_report.explained_total_effect,
                "residual_tolerance": pnl_report.residual_tolerance,
            },
            pnl["expected"],
            abs_tol=abs_tol,
        )

    if "var" in scenario:
        var = scenario["var"]
        var_report = run_historical_var(
            normalize_positions(var["positions"]),
            var["historical_returns"],
            as_of="2026-06-04T12:00:00Z",
            run_id=scenario["scenario_id"],
        )
        _assert_float_map(var_report.var_by_confidence, var["expected"]["var_by_confidence"], abs_tol=abs_tol)
        for actual, expected in zip(var_report.scenario_pnl, var["expected"]["scenario_pnl"], strict=True):
            assert actual["date"] == expected["date"]
            assert actual["pnl"] == pytest.approx(expected["pnl"], abs=abs_tol)

    if "greeks" in scenario:
        greeks = scenario["greeks"]
        greeks_report = run_black76_greeks(greeks["rows"], run_id=scenario["scenario_id"])
        assert greeks_report.model_convention == greeks["expected"]["model_convention"]
        for actual, expected in zip(greeks_report.greeks, greeks["expected"]["greeks"], strict=True):
            _assert_float_map(
                {key: actual[key] for key in expected},
                expected,
                abs_tol=greeks_abs_tol,
            )


def test_historical_var_missing_factor_fails_closed():
    scenario = _scenario("flat_single_leg.json")
    var = scenario["var"]
    bad_returns = [dict(row, risk_factor="PJM.WH.RT.FULL_LMP.ATC.BAD") for row in var["historical_returns"]]

    with pytest.raises(WorkbenchException) as exc:
        run_historical_var(
            normalize_positions(var["positions"]),
            bad_returns,
            as_of="2026-06-04T12:00:00Z",
            run_id="missing-factor",
        )

    assert exc.value.code == VALUATION_INSUFFICIENT_DATA
    assert "missing returns for risk factors" in exc.value.message


def test_historical_var_accepts_typed_risk_factor_identifiers():
    scenario = _scenario("calendar_spread.json")
    var = scenario["var"]
    typed_returns = [dict(row, risk_factor=RiskFactorId(row["risk_factor"])) for row in var["historical_returns"]]

    report = run_historical_var(
        normalize_positions(var["positions"]),
        typed_returns,
        as_of="2026-06-04T12:00:00Z",
        run_id="typed-factor-calendar-spread",
    )

    assert report.var_by_confidence["95"] == pytest.approx(404.0)
    assert report.lineage["risk_factors"] == [
        "PJM.WH.RT.FULL_LMP.ATC.N26",
        "PJM.WH.RT.FULL_LMP.ATC.Q126",
    ]


def test_historical_var_malformed_factor_fails_at_construction():
    scenario = _scenario("flat_single_leg.json")
    var = scenario["var"]
    bad_returns = [dict(row, risk_factor={"value": row["risk_factor"]}) for row in var["historical_returns"]]

    with pytest.raises(WorkbenchException) as exc:
        run_historical_var(
            normalize_positions(var["positions"]),
            bad_returns,
            as_of="2026-06-04T12:00:00Z",
            run_id="malformed-factor",
        )

    assert exc.value.code == VALUATION_INSUFFICIENT_DATA
    assert "risk factor must be a RiskFactorId or string" in exc.value.message


def test_risk_factor_id_rejects_empty_values():
    with pytest.raises(ValueError):
        RiskFactorId("")


def test_pnl_injected_attribution_bug_fails_independent_tie_out(monkeypatch):
    scenario = _scenario("flat_single_leg.json")
    pnl = scenario["pnl"]
    original_q = pnl_service._q

    def wrong_quantity(position):
        return original_q(position) * 2.0

    monkeypatch.setattr(pnl_service, "_q", wrong_quantity)

    with pytest.raises(WorkbenchException) as exc:
        run_pnl_attribution(
            normalize_positions(pnl["prior_positions"]),
            normalize_positions(pnl["current_positions"]),
            run_id="injected-pnl-bug",
        )

    assert exc.value.code == VALUATION_TIE_OUT_FAILED
    assert "residual_cause=bridge_exceeds_tolerance" in exc.value.message
