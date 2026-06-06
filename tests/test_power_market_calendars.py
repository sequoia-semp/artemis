from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from pga_workbench.core.calendars import holiday_dates, is_calendar_holiday, load_power_market_calendars
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.registry import validate_registries


ROOT = Path(__file__).resolve().parents[1]


def test_power_market_calendar_registry_validates():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")
    calendars = load_power_market_calendars(ROOT / "registries")

    assert "power_market_calendars.yaml" in result.validated_files
    assert result.warnings == []
    assert calendars["NERC_HOLIDAYS"]["calendar_type"] == "holiday_calendar"
    assert calendars["PJM_EPT_POWER_DAY"]["holiday_calendar"] == "NERC_HOLIDAYS"


def test_nerc_holidays_are_resolved_from_registry_rules():
    holidays = holiday_dates("NERC_HOLIDAYS", 2026, ROOT / "registries")

    assert date(2026, 1, 1) in holidays
    assert date(2026, 5, 25) in holidays
    assert date(2026, 7, 4) in holidays
    assert date(2026, 9, 7) in holidays
    assert date(2026, 11, 26) in holidays
    assert date(2026, 12, 25) in holidays
    assert is_calendar_holiday(date(2026, 7, 4), "NERC_HOLIDAYS", ROOT / "registries")
    assert not is_calendar_holiday(date(2026, 7, 5), "NERC_HOLIDAYS", ROOT / "registries")


def test_unknown_calendar_fails_closed():
    with pytest.raises(WorkbenchException) as exc:
        holiday_dates("UNKNOWN_CALENDAR", 2026, ROOT / "registries")

    assert exc.value.code == "POWER_CALENDAR_ERROR"
