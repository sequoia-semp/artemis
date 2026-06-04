import pytest
from pga_workbench.spreads import decompose_power_spread
from pga_workbench.exceptions import WorkbenchException, NON_CANONICAL_BASIS_ORIENTATION


def test_allowed_edges():
    for edge in ["WH/AD", "AD/NI", "WH/NI"]:
        assert decompose_power_spread(edge, 25).quote_label == edge


def test_forbidden_edges_fail_closed():
    for edge in ["AD/WH", "NI/AD", "NI/WH"]:
        with pytest.raises(WorkbenchException) as e:
            decompose_power_spread(edge, 25)
        assert e.value.code == NON_CANONICAL_BASIS_ORIENTATION


def test_short_canonical_spread_leg_exposures():
    ex = decompose_power_spread("WH/AD", -25)
    assert ex.first == "WH"
    assert ex.second == "AD"
    assert ex.first_leg_exposure == -25
    assert ex.second_leg_exposure == 25
