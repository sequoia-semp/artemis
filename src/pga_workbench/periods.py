from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List

from .exceptions import WorkbenchException, UNKNOWN_PERIOD

MONTH_CODES = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}
MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


@dataclass(frozen=True)
class PeriodExpression:
    raw_label: str
    normalized_label: str
    period_type: str
    months: List[str]
    commodity_context: str = "generic"
    strip_weighting_rule: str = "custom"
    balmo_excludes_next_day: bool = False


def _year(yy: str) -> int:
    y = int(yy)
    if y < 100:
        return 2000 + y
    return y


def _month_label(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month]}{str(year)[-2:]}"


def _months_range(start_year: int, start_month: int, end_year: int, end_month: int) -> list[str]:
    out = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        out.append(_month_label(y, m))
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


def parse_period(raw: str, commodity_context: str = "generic") -> PeriodExpression:
    s = raw.strip().upper().replace(" ", "")
    weighting = "power_reference_hours" if commodity_context == "power" else "gas_delivery_days" if commodity_context == "gas" else "custom"

    if s == "BALMO":
        return PeriodExpression(raw, "BALMO", "balance_of_month", [], commodity_context, weighting, True)

    m = re.fullmatch(r"PY(\d{2}|\d{4})", s)
    if m:
        y = _year(m.group(1))
        months = _months_range(y, 6, y + 1, 5)
        return PeriodExpression(raw, f"PY{str(y)[-2:]}", "planning_year", months, commodity_context, weighting, False)

    m = re.fullmatch(r"X(\d{2}|\d{4})H(\d{2}|\d{4})", s)
    if m:
        y1, y2 = _year(m.group(1)), _year(m.group(2))
        months = _months_range(y1, 11, y2, 3)
        return PeriodExpression(raw, f"X{str(y1)[-2:]}H{str(y2)[-2:]}", "gas_winter_xh", months, commodity_context, weighting, False)

    m = re.fullmatch(r"JV(\d{2}|\d{4})", s)
    if m:
        y = _year(m.group(1))
        months = _months_range(y, 4, y, 10)
        return PeriodExpression(raw, f"JV{str(y)[-2:]}", "gas_summer_jv", months, commodity_context, weighting, False)

    m = re.fullmatch(r"CAL(\d{2}|\d{4})", s)
    if m:
        y = _year(m.group(1))
        months = _months_range(y, 1, y, 12)
        return PeriodExpression(raw, f"CAL{str(y)[-2:]}", "calendar_year", months, commodity_context, weighting, False)

    m = re.fullmatch(r"Q([1-4])(\d{2}|\d{4})", s)
    if m:
        q, y = int(m.group(1)), _year(m.group(2))
        start = 3 * (q - 1) + 1
        months = _months_range(y, start, y, start + 2)
        return PeriodExpression(raw, f"Q{q}{str(y)[-2:]}", "quarter", months, commodity_context, weighting, False)

    m = re.fullmatch(r"([FGHJKMNQUVXZ]{2})(\d{2}|\d{4})", s)
    if m:
        codes, y = m.group(1), _year(m.group(2))
        start_m, end_m = MONTH_CODES[codes[0]], MONTH_CODES[codes[1]]
        if start_m > end_m:
            raise WorkbenchException(UNKNOWN_PERIOD, f"Month range crosses year or is unsupported: {raw}")
        months = _months_range(y, start_m, y, end_m)
        return PeriodExpression(raw, f"{codes}{str(y)[-2:]}", "month_range", months, commodity_context, weighting, False)

    m = re.fullmatch(r"([FGHJKMNQUVXZ])(\d{2}|\d{4})", s)
    if m:
        code, y = m.group(1), _year(m.group(2))
        month = MONTH_CODES[code]
        return PeriodExpression(raw, f"{code}{str(y)[-2:]}", "month", [_month_label(y, month)], commodity_context, weighting, False)

    raise WorkbenchException(UNKNOWN_PERIOD, f"Cannot parse period expression: {raw}")
