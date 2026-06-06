from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..core.calendars import is_calendar_holiday
from ..exceptions import WorkbenchException
from ..models import PowerPriceShapeState, PriceSurfacePoint
from ..registry import load_yaml_unique
from ..registry_access import DEFAULT_REGISTRY_DIR
from ..serialization import to_plain

POWER_PRICE_SHAPE_ERROR = "POWER_PRICE_SHAPE_ERROR"


def load_power_price_shape_rules(registry_dir: Path) -> dict[str, dict[str, Any]]:
    payload = load_yaml_unique(Path(registry_dir) / "power_price_shape_rules.yaml")
    if not isinstance(payload, dict):
        raise WorkbenchException(POWER_PRICE_SHAPE_ERROR, "power_price_shape_rules.yaml must be a mapping")
    return {str(key): dict(value) for key, value in payload.items()}


def _parse_ept(value: Any, label: str) -> datetime:
    raw = str(value).strip()
    if not raw:
        raise WorkbenchException(POWER_PRICE_SHAPE_ERROR, f"{label} is required")
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise WorkbenchException(POWER_PRICE_SHAPE_ERROR, f"{label} is not a recognized timestamp: {value}") from exc


def is_nerc_holiday(day: date, registry_dir: Path = DEFAULT_REGISTRY_DIR) -> bool:
    return is_calendar_holiday(day, "NERC_HOLIDAYS", registry_dir)


def _hour_ending(start_ept: datetime) -> int:
    return 24 if start_ept.hour == 23 else start_ept.hour + 1


def _expected_hours(rule: dict[str, Any], day: date, registry_dir: Path) -> set[int]:
    holiday_calendar = rule.get("holiday_calendar")
    if holiday_calendar and is_calendar_holiday(day, str(holiday_calendar), registry_dir):
        return {int(item) for item in rule.get("holiday_hours_ending") or []}
    if day.weekday() >= 5:
        return {int(item) for item in rule.get("weekend_hours_ending") or []}
    return {int(item) for item in rule.get("weekday_hours_ending") or []}


def _index_parts(point: PriceSurfacePoint) -> tuple[str, str, str]:
    parts = point.index_id.split(".")
    if len(parts) < 6 or parts[0] != "PJM" or parts[3] != "FULL_LMP" or parts[4] != "HOURLY":
        raise WorkbenchException(POWER_PRICE_SHAPE_ERROR, f"Expected PJM hourly full-LMP point, got {point.index_id}")
    return parts[1], parts[2], parts[3]


def _is_hourly_full_lmp_point(point: PriceSurfacePoint) -> bool:
    parts = point.index_id.split(".")
    return len(parts) >= 6 and parts[0] == "PJM" and parts[3] == "FULL_LMP" and parts[4] == "HOURLY"


def _point_ept_start(point: PriceSurfacePoint) -> datetime:
    value = point.lineage.get("delivery_start_ept")
    if value is None:
        raise WorkbenchException(POWER_PRICE_SHAPE_ERROR, f"Hourly point missing delivery_start_ept lineage: {point.index_id}")
    return _parse_ept(value, "delivery_start_ept")


def _group_hourly_points(points: list[PriceSurfacePoint]) -> dict[tuple[str, str, date], dict[int, PriceSurfacePoint]]:
    grouped: dict[tuple[str, str, date], dict[int, PriceSurfacePoint]] = defaultdict(dict)
    for point in points:
        location_id, market_run, _component = _index_parts(point)
        start_ept = _point_ept_start(point)
        day = start_ept.date()
        hour = _hour_ending(start_ept)
        key = (location_id, market_run, day)
        if hour in grouped[key]:
            raise WorkbenchException(POWER_PRICE_SHAPE_ERROR, f"Duplicate hourly point for {location_id} {market_run} {day} HE{hour}")
        grouped[key][hour] = point
    return grouped


def _rollup_point(rule_id: str, rule: dict[str, Any], key: tuple[str, str, date], hourly: list[PriceSurfacePoint], as_of: str) -> PriceSurfacePoint:
    location_id, market_run, day = key
    shape = str(rule["shape"])
    period_id = "DAY_" + day.strftime("%Y%m%d")
    index_base = f"PJM.{location_id}.{market_run}.FULL_LMP.{shape}"
    price = sum(float(point.price) for point in hourly) / len(hourly)
    return PriceSurfacePoint(
        as_of=as_of,
        index_id=f"{index_base}.{period_id}",
        location_id=location_id,
        commodity="power",
        period_id=period_id,
        price=price,
        quote_unit="USD_per_MWh",
        source="Artemis deterministic rollup",
        source_role="derived_from_authoritative_iso_publication",
        lineage={
            "rule_id": rule_id,
            "shape": shape,
            "market_run": market_run,
            "location_id": location_id,
            "input_index_ids": [point.index_id for point in hourly],
            "input_hour_count": len(hourly),
            "aggregation": rule["aggregation"],
            "hour_basis": rule["hour_basis"],
            "calendar": rule["calendar"],
        },
    )


def rollup_hourly_prices_to_daily_shapes(
    points: list[PriceSurfacePoint],
    registry_dir: Path,
    as_of: str,
    run_id: str = "power-price-shape-rollup",
    rule_ids: list[str] | None = None,
) -> PowerPriceShapeState:
    rules = load_power_price_shape_rules(registry_dir)
    selected_rule_ids = rule_ids or list(rules)
    full_lmp_points = [point for point in points if _is_hourly_full_lmp_point(point)]
    grouped = _group_hourly_points(full_lmp_points)
    rollups: list[PriceSurfacePoint] = []
    gaps: list[dict[str, Any]] = []

    for key, hours_by_ending in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1], item[0][2])):
        location_id, market_run, day = key
        for rule_id in selected_rule_ids:
            if rule_id not in rules:
                raise WorkbenchException(POWER_PRICE_SHAPE_ERROR, f"Unknown power price shape rule: {rule_id}")
            rule = rules[rule_id]
            expected = _expected_hours(rule, day, registry_dir)
            if not expected:
                continue
            observed = expected & set(hours_by_ending)
            if observed != expected:
                gaps.append(
                    {
                        "rule_id": rule_id,
                        "location_id": location_id,
                        "market_run": market_run,
                        "date": day.isoformat(),
                        "reason": "missing_hourly_source_prices",
                        "expected_hours": len(expected),
                        "observed_hours": len(observed),
                    }
                )
                continue
            hourly = [hours_by_ending[hour] for hour in sorted(expected)]
            rollups.append(_rollup_point(rule_id, rule, key, hourly, as_of))

    return PowerPriceShapeState(
        run_id=run_id,
        as_of=as_of,
        source_points=[to_plain(point) for point in points],
        price_surface_points=[to_plain(point) for point in rollups],
        gaps=gaps,
        lineage={
            "source_point_count": len(points),
            "eligible_full_lmp_source_point_count": len(full_lmp_points),
            "rollup_count": len(rollups),
            "gap_count": len(gaps),
            "rule_ids": selected_rule_ids,
        },
    )


def _price_shape_view_payload(payload: dict[str, Any], run_id: str) -> dict[str, Any]:
    points = sorted(
        list(payload["price_surface_points"]),
        key=lambda item: (
            str(item.get("location_id")),
            str(item.get("lineage", {}).get("market_run")),
            str(item.get("lineage", {}).get("shape")),
            str(item.get("period_id")),
        ),
    )
    gaps = list(payload["gaps"])
    lineage = dict(payload.get("lineage") or {})
    shape_prices = [
        {
            "index_id": str(point["index_id"]),
            "location_id": str(point["location_id"]),
            "market_run": str(point.get("lineage", {}).get("market_run")),
            "shape": str(point.get("lineage", {}).get("shape")),
            "period_id": str(point["period_id"]),
            "price": float(point["price"]),
            "quote_unit": str(point["quote_unit"]),
            "source_role": str(point["source_role"]),
        }
        for point in points
    ]
    summary = (
        "Power price shape rollups built from source-backed hourly prices: "
        f"{len(shape_prices)} derived shape prices, {len(gaps)} explicit gaps."
    )
    drivers: list[dict[str, Any]] = [
        {
            "name": "derived_price_shape_count",
            "direction": "source_observed",
            "value": len(shape_prices),
            "unit": "count",
            "source_artifact": "power_price_shape_rollups",
        },
        {
            "name": "price_shape_gap_count",
            "direction": "gap_observed" if gaps else "no_gap_observed",
            "value": len(gaps),
            "unit": "count",
            "source_artifact": "power_price_shape_rollups",
        },
    ]
    if shape_prices:
        first = shape_prices[0]
        drivers.append(
            {
                "name": "first_price_shape",
                "direction": "source_observed",
                "location_id": first["location_id"],
                "market_run": first["market_run"],
                "shape": first["shape"],
                "value": first["price"],
                "unit": first["quote_unit"],
                "source_artifact": "power_price_shape_rollups",
            }
        )

    return {
        "summary": summary,
        "stance_summary": "Price shapes are deterministic source-backed context only; no trading stance is inferred.",
        "market_scope": {
            "commodity": "power",
            "regions": ["PJM"],
            "exchange_scope": [],
        },
        "drivers": drivers,
        "current_day_view": {
            "price_shapes": {
                "shape_prices": shape_prices,
                "gaps": gaps,
                "rollup_count": int(lineage.get("rollup_count") or len(shape_prices)),
                "gap_count": int(lineage.get("gap_count") or len(gaps)),
                "source_point_count": int(lineage.get("source_point_count") or 0),
            }
        },
        "evidence": [
            {
                "source": "Artemis deterministic rollup",
                "artifact": "power_price_shape_rollups",
                "run_id": run_id,
                "rollup_count": int(lineage.get("rollup_count") or len(shape_prices)),
                "gap_count": int(lineage.get("gap_count") or len(gaps)),
                "rule_ids": list(lineage.get("rule_ids") or []),
            }
        ],
    }


def build_power_price_shape_artifacts(
    points: list[PriceSurfacePoint],
    registry_dir: Path,
    as_of: str,
    run_id: str = "power-price-shape-rollup",
    rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    state = rollup_hourly_prices_to_daily_shapes(points, registry_dir, as_of, run_id=run_id, rule_ids=rule_ids)
    payload = to_plain(state)
    return {
        "power_price_shape_rollups": payload,
        "price_surface_points": payload["price_surface_points"],
        "shape_gaps": payload["gaps"],
        "source_lineage": [
            {
                "source": "Artemis deterministic rollup",
                "artifact": "power_price_shape_rollups",
                "run_id": run_id,
            }
        ],
        **_price_shape_view_payload(payload, run_id),
    }


def validate_power_price_shape_state(state: PowerPriceShapeState | dict[str, Any], schema_dir: Path) -> None:
    schema = load_yaml_unique(Path(schema_dir) / "power_price_shape_state.schema.json")
    payload = to_plain(state)
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(POWER_PRICE_SHAPE_ERROR, f"power price shape state{suffix}: {first.message}")
