import pytest
from pga_workbench.atc import decompose_atc, atc_blended_price
from pga_workbench.vol import validate_vol_location, absolute_iv_from_atm_diff, risk_reversal
from pga_workbench.exceptions import WorkbenchException, UNSUPPORTED_VOL_SURFACE


def test_atc_decomposition_equal_mw():
    d = decompose_atc(25)
    assert [(c.shape, c.signed_mw) for c in d.components] == [("PEAK", 25), ("OFFPEAK", 25)]


def test_atc_blended_price_hour_weighted():
    assert atc_blended_price(100, 50, 10, 30) == 62.5


def test_wh_hh_vol_in_mvp():
    validate_vol_location("WH")
    validate_vol_location("HH")


def test_non_mvp_vol_blocked():
    with pytest.raises(WorkbenchException) as e:
        validate_vol_location("TETCO_M3")
    assert e.value.code == UNSUPPORTED_VOL_SURFACE


def test_skew_diff_to_atm_and_rr():
    assert absolute_iv_from_atm_diff(0.80, 0.05) == pytest.approx(0.85)
    assert risk_reversal(0.85, 0.78) == pytest.approx(0.07)
