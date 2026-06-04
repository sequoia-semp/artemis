from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Horizon:
    type: str
    start_date: date
    center_date: date
    end_date: date

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.type,
            "start_date": self.start_date.isoformat(),
            "center_date": self.center_date.isoformat(),
            "end_date": self.end_date.isoformat(),
        }


def plus_minus_days(as_of: date, days: int = 14) -> Horizon:
    return Horizon(
        type=f"plus_minus_{days}_day",
        start_date=as_of - timedelta(days=days),
        center_date=as_of,
        end_date=as_of + timedelta(days=days),
    )


def prior_day(as_of: date) -> date:
    return as_of - timedelta(days=1)


def current_day(as_of: date) -> date:
    return as_of


def single_day_horizon(as_of: date, horizon_type: str) -> Horizon:
    return Horizon(type=horizon_type, start_date=as_of, center_date=as_of, end_date=as_of)
