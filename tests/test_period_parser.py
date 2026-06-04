from pga_workbench.periods import parse_period


def test_planning_year():
    p = parse_period("PY26", "power")
    assert p.months == ["Jun26", "Jul26", "Aug26", "Sep26", "Oct26", "Nov26", "Dec26", "Jan27", "Feb27", "Mar27", "Apr27", "May27"]
    assert p.period_type == "planning_year"


def test_gas_winter_xh():
    p = parse_period("X26H27", "gas")
    assert p.months == ["Nov26", "Dec26", "Jan27", "Feb27", "Mar27"]
    assert p.period_type == "gas_winter_xh"


def test_gas_summer_jv():
    p = parse_period("JV27", "gas")
    assert p.months == ["Apr27", "May27", "Jun27", "Jul27", "Aug27", "Sep27", "Oct27"]
    assert p.period_type == "gas_summer_jv"


def test_power_fg_nq():
    assert parse_period("FG26", "power").months == ["Jan26", "Feb26"]
    assert parse_period("NQ26", "power").months == ["Jul26", "Aug26"]


def test_quarter_cal_balmo():
    assert parse_period("Q126").months == ["Jan26", "Feb26", "Mar26"]
    assert len(parse_period("Cal26").months) == 12
    assert parse_period("BALMO").balmo_excludes_next_day is True
