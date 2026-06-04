from __future__ import annotations

from datetime import date

from pga_workbench.analyst.horizons import current_day, plus_minus_days, prior_day


def test_plus_minus_fourteen_day_horizon():
    horizon = plus_minus_days(date(2026, 6, 4))

    assert horizon.start_date == date(2026, 5, 21)
    assert horizon.center_date == date(2026, 6, 4)
    assert horizon.end_date == date(2026, 6, 18)


def test_prior_and_current_day_helpers():
    as_of = date(2026, 6, 4)

    assert prior_day(as_of) == date(2026, 6, 3)
    assert current_day(as_of) == as_of
