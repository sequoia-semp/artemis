from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from ..models import GreeksReport
from ..vol import validate_vol_location


def read_option_rows(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black76_greeks(option_type: str, forward: float, strike: float, volatility: float, time_to_expiry_years: float, discount_factor: float = 1.0) -> dict[str, float]:
    if forward <= 0 or strike <= 0 or volatility <= 0 or time_to_expiry_years <= 0:
        raise ValueError("Black-76 inputs must be positive")
    sigma_root_t = volatility * math.sqrt(time_to_expiry_years)
    d1 = (math.log(forward / strike) + 0.5 * volatility * volatility * time_to_expiry_years) / sigma_root_t
    d2 = d1 - sigma_root_t
    option = option_type.lower()
    if option == "call":
        price = discount_factor * (forward * _norm_cdf(d1) - strike * _norm_cdf(d2))
        delta = discount_factor * _norm_cdf(d1)
        theta = -discount_factor * forward * _norm_pdf(d1) * volatility / (2.0 * math.sqrt(time_to_expiry_years))
    elif option == "put":
        price = discount_factor * (strike * _norm_cdf(-d2) - forward * _norm_cdf(-d1))
        delta = -discount_factor * _norm_cdf(-d1)
        theta = -discount_factor * forward * _norm_pdf(d1) * volatility / (2.0 * math.sqrt(time_to_expiry_years))
    else:
        raise ValueError(f"Unsupported option_type: {option_type}")
    gamma = discount_factor * _norm_pdf(d1) / (forward * sigma_root_t)
    vega = discount_factor * forward * _norm_pdf(d1) * math.sqrt(time_to_expiry_years)
    return {"price": price, "delta": delta, "gamma": gamma, "vega": vega, "theta": theta}


def run_black76_greeks(rows: list[dict[str, Any]], run_id: str = "greeks-run") -> GreeksReport:
    greeks = []
    for row in rows:
        validate_vol_location(str(row["location_id"]))
        base = black76_greeks(
            option_type=str(row["option_type"]),
            forward=float(row["forward"]),
            strike=float(row["strike"]),
            volatility=float(row["volatility"]),
            time_to_expiry_years=float(row["time_to_expiry_years"]),
            discount_factor=float(row.get("discount_factor") or 1.0),
        )
        position = float(row.get("position") or 1.0)
        greeks.append(
            {
                "option_id": row.get("option_id") or row.get("underlying_index_id"),
                "location_id": row["location_id"],
                "underlying_index_id": row["underlying_index_id"],
                "delivery_period_id": row["delivery_period_id"],
                "option_type": row["option_type"],
                "model_price": base["price"],
                "position_delta": base["delta"] * position,
                "position_gamma": base["gamma"] * position,
                "position_vega": base["vega"] * position,
                "position_theta": base["theta"] * position,
            }
        )
    return GreeksReport(
        run_id=run_id,
        as_of=str(rows[0]["as_of"]) if rows else "",
        model_convention="Black76",
        greeks=greeks,
        lineage={"vol_scope": "WH_HH_only"},
    )
