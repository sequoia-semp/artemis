from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from ..registry_access import DEFAULT_REGISTRY_DIR

POWER_CALENDAR_ERROR = "POWER_CALENDAR_ERROR"

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def load_power_market_calendars(registry_dir: Path = DEFAULT_REGISTRY_DIR) -> dict[str, dict[str, Any]]:
    payload = load_yaml_unique(Path(registry_dir) / "power_market_calendars.yaml")
    if not isinstance(payload, dict):
        raise WorkbenchException(POWER_CALENDAR_ERROR, "power_market_calendars.yaml must be a mapping")
    return {str(key): dict(value) for key, value in payload.items()}


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    found = 0
    day = date(year, month, 1)
    while day.month == month:
        if day.weekday() == weekday:
            found += 1
            if found == nth:
                return day
        day = date.fromordinal(day.toordinal() + 1)
    raise WorkbenchException(POWER_CALENDAR_ERROR, f"No weekday {weekday} occurrence {nth} in {year}-{month}")


def _last_weekday(year: int, month: int, weekday: int) -> date:
    day = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
    day = date.fromordinal(day.toordinal() - 1)
    while day.weekday() != weekday:
        day = date.fromordinal(day.toordinal() - 1)
    return day


def _holiday_date(year: int, rule: dict[str, Any]) -> date:
    rule_type = str(rule["rule_type"])
    month = int(rule["month"])
    if rule_type == "fixed_date":
        return date(year, month, int(rule["day"]))
    weekday = WEEKDAYS[str(rule["weekday"])]
    if rule_type == "nth_weekday":
        return _nth_weekday(year, month, weekday, int(rule["nth"]))
    if rule_type == "last_weekday":
        return _last_weekday(year, month, weekday)
    raise WorkbenchException(POWER_CALENDAR_ERROR, f"Unsupported holiday rule type: {rule_type}")


def holiday_dates(calendar_id: str, year: int, registry_dir: Path = DEFAULT_REGISTRY_DIR) -> set[date]:
    calendars = load_power_market_calendars(registry_dir)
    calendar = calendars.get(calendar_id)
    if calendar is None:
        raise WorkbenchException(POWER_CALENDAR_ERROR, f"Unknown power market calendar: {calendar_id}")
    if calendar.get("calendar_type") != "holiday_calendar":
        raise WorkbenchException(POWER_CALENDAR_ERROR, f"Calendar is not a holiday calendar: {calendar_id}")
    return {_holiday_date(year, dict(rule)) for rule in calendar.get("holiday_rules") or []}


def is_calendar_holiday(day: date, calendar_id: str, registry_dir: Path = DEFAULT_REGISTRY_DIR) -> bool:
    return day in holiday_dates(calendar_id, day.year, registry_dir)
