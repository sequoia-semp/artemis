from __future__ import annotations

import csv
from pathlib import Path

from ..models import ForecastSnapshot, FundamentalObservation


def load_pjm_fundamental_fixture(path: Path) -> tuple[list[FundamentalObservation], list[ForecastSnapshot]]:
    observations: list[FundamentalObservation] = []
    forecasts: list[ForecastSnapshot] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=1):
            source = row.get("source") or "PJM"
            lineage = {"fixture_path": str(path), "raw_row_id": str(row_number)}
            if row["record_type"] == "forecast":
                forecasts.append(
                    ForecastSnapshot(
                        as_of=row["as_of"],
                        source=source,
                        forecast_type=row["metric"],
                        location_id=row["location_id"],
                        delivery_start=row["delivery_start"],
                        delivery_end=row["delivery_end"],
                        value=float(row["value"]),
                        unit=row["unit"],
                        vintage=row.get("vintage") or row["as_of"],
                        lineage=lineage,
                    )
                )
            else:
                observations.append(
                    FundamentalObservation(
                        as_of=row["as_of"],
                        source=source,
                        metric=row["metric"],
                        location_id=row["location_id"],
                        delivery_start=row["delivery_start"],
                        delivery_end=row["delivery_end"],
                        value=float(row["value"]),
                        unit=row["unit"],
                        lineage=lineage,
                    )
                )
    return observations, forecasts
