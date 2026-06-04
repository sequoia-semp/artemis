"""Quantity conventions.

Critical v0.1 gas convention:
    1 contract = 0.25/d = 2,500 MMBtu/day
    1.0/d = 4 contracts = 10,000 MMBtu/day
"""

MMBTU_PER_GAS_CONTRACT_PER_DAY = 2500.0
D_PER_GAS_CONTRACT = 0.25
CONTRACTS_PER_1D = 4.0
MMBTU_PER_1D_PER_DAY = 10000.0


def gas_contracts_to_daily_d(contracts: float) -> float:
    return contracts * D_PER_GAS_CONTRACT


def daily_d_to_gas_contracts(d_per_day: float) -> float:
    return d_per_day * CONTRACTS_PER_1D


def gas_contracts_to_total_mmbtu(contracts: float, delivery_days: int) -> float:
    return contracts * MMBTU_PER_GAS_CONTRACT_PER_DAY * delivery_days


def power_mw_to_mwh(mw: float, reference_hours: float) -> float:
    return mw * reference_hours
