from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..models import HistoricalVaRReport, NormalizedPosition


def read_historical_returns(path: Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {"date": row["date"], "risk_factor": row["risk_factor"], "return": float(row["return"])}
        for row in rows
    ]


def _position_risk_factor(position: NormalizedPosition) -> str:
    return str(position.normalized["index_id"])


def _historical_quantile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        return 0.0
    index = int(probability * (len(sorted_values) - 1))
    return sorted_values[index]


def run_historical_var(
    positions: list[NormalizedPosition],
    historical_returns: list[dict[str, Any]],
    as_of: str,
    run_id: str = "var-run",
    confidence_levels: list[float] | None = None,
) -> HistoricalVaRReport:
    confidence_levels = confidence_levels or [0.95, 0.99]
    exposure_by_factor: dict[str, float] = {}
    for position in positions:
        exposure_by_factor[_position_risk_factor(position)] = exposure_by_factor.get(_position_risk_factor(position), 0.0) + float(position.derived.get("market_value") or 0.0)

    pnl_by_date: dict[str, float] = {}
    for row in historical_returns:
        exposure = exposure_by_factor.get(str(row["risk_factor"]), 0.0)
        pnl_by_date[str(row["date"])] = pnl_by_date.get(str(row["date"]), 0.0) + exposure * float(row["return"])

    scenario_pnl = [{"date": date, "pnl": pnl} for date, pnl in sorted(pnl_by_date.items())]
    sorted_pnl = sorted(float(row["pnl"]) for row in scenario_pnl)
    var_by_confidence = {}
    for confidence in confidence_levels:
        tail_pnl = _historical_quantile(sorted_pnl, 1.0 - confidence)
        var_by_confidence[f"{int(confidence * 100)}"] = max(0.0, -tail_pnl)

    return HistoricalVaRReport(
        run_id=run_id,
        as_of=as_of,
        method="historical_simulation",
        horizon_days=1,
        confidence_levels=confidence_levels,
        lookback_observations=len(scenario_pnl),
        var_by_confidence=var_by_confidence,
        scenario_pnl=scenario_pnl,
        lineage={"risk_factors": sorted(exposure_by_factor)},
    )
