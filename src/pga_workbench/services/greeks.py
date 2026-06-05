from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from ..models import GreeksReport
from ..registry_access import find_option_contract
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


def _registered_option_contract(row: dict[str, Any]) -> dict[str, Any] | None:
    option_key = row.get("option_contract_id") or row.get("option_symbol")
    if not option_key:
        return None
    return find_option_contract(str(option_key))


def run_black76_greeks(rows: list[dict[str, Any]], run_id: str = "greeks-run") -> GreeksReport:
    greeks = []
    exceptions = []
    for row in rows:
        contract = _registered_option_contract(row)
        location_id = str(contract["location_id"] if contract else row["location_id"])
        underlying_index_id = str(contract["underlying_index_id"] if contract else row["underlying_index_id"])
        validate_vol_location(location_id)
        base = black76_greeks(
            option_type=str(row["option_type"]),
            forward=float(row["forward"]),
            strike=float(row["strike"]),
            volatility=float(row["volatility"]),
            time_to_expiry_years=float(row["time_to_expiry_years"]),
            discount_factor=float(row.get("discount_factor") or 1.0),
        )
        position = float(row.get("position") or 1.0)
        greek = {
            "option_id": row.get("option_id") or row.get("option_contract_id") or row.get("underlying_index_id"),
            "option_contract_id": None if contract is None else contract["option_contract_id"],
            "contract_symbol": None if contract is None else contract["contract_symbol"],
            "exchange": None if contract is None else contract["exchange"],
            "location_id": location_id,
            "underlying_index_id": underlying_index_id,
            "delivery_period_id": row["delivery_period_id"],
            "option_type": row["option_type"],
            "option_style": None if contract is None else contract["option_style"],
            "exercise_method": None if contract is None else contract["exercise_method"],
            "strike": float(row["strike"]),
            "forward": float(row["forward"]),
            "volatility": float(row["volatility"]),
            "time_to_expiry_years": float(row["time_to_expiry_years"]),
            "premium_quote_unit": None if contract is None else contract["premium_quote_unit"],
            "strike_unit": None if contract is None else contract["strike_unit"],
            "contract_size": None if contract is None else contract["contract_size"],
            "model_price": base["price"],
            "position_delta": base["delta"] * position,
            "position_gamma": base["gamma"] * position,
            "position_vega": base["vega"] * position,
            "position_theta": base["theta"] * position,
            "model_scope": "unregistered_row_input" if contract is None else contract["model_scope"],
        }
        if contract is not None and contract["option_style"] != "European":
            exceptions.append(
                {
                    "code": "OPTION_STYLE_APPROXIMATION",
                    "option_contract_id": contract["option_contract_id"],
                    "message": "Black76 Greeks are screening analytics for non-European exercise style; exercise optionality is not modeled.",
                    "blocking": False,
                }
            )
        greeks.append(greek)
    return GreeksReport(
        run_id=run_id,
        as_of=str(rows[0]["as_of"]) if rows else "",
        model_convention="Black76",
        greeks=greeks,
        lineage={"vol_scope": "WH_HH_only", "exceptions": exceptions},
    )
