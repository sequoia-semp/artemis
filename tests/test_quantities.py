from pga_workbench.quantities import (
    gas_contracts_to_daily_d,
    daily_d_to_gas_contracts,
    gas_contracts_to_total_mmbtu,
    power_mw_to_mwh,
)


def test_single_gas_contract_is_point25d():
    assert gas_contracts_to_daily_d(1) == 0.25


def test_one_d_is_four_contracts():
    assert daily_d_to_gas_contracts(1.0) == 4


def test_gas_total_mmbtu():
    assert gas_contracts_to_total_mmbtu(1, 31) == 2500 * 31
    assert gas_contracts_to_total_mmbtu(4, 31) == 10000 * 31


def test_power_mw_to_mwh():
    assert power_mw_to_mwh(25, 400) == 10000
