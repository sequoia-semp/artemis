from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..exceptions import WorkbenchException
from ..models import ForecastSnapshot, FundamentalObservation, FundamentalState
from ..registry import load_yaml_unique
from ..serialization import to_plain

FUNDAMENTALS_ERROR = "FUNDAMENTALS_ERROR"
UNKNOWN_PJM_LOAD_AREA = "UNKNOWN_PJM_LOAD_AREA"

BEST_ACTUAL_METRIC = "PJM.LOAD.ACTUAL.HOURLY_MW"
SEVEN_DAY_ERROR_METRIC = "PJM.LOAD.FORECAST_ERROR.SEVEN_DAY.HOURLY_MW"


def load_pjm_fundamental_feeds(registry_dir: Path) -> dict[str, dict[str, Any]]:
    payload = load_yaml_unique(Path(registry_dir) / "pjm_fundamental_feeds.yaml")
    if not isinstance(payload, dict):
        raise WorkbenchException(FUNDAMENTALS_ERROR, "pjm_fundamental_feeds.yaml must be a mapping")
    return {str(key): dict(value) for key, value in payload.items()}


def load_pjm_load_area_aliases(registry_dir: Path) -> dict[str, str]:
    payload = load_yaml_unique(Path(registry_dir) / "pjm_load_areas.yaml")
    if not isinstance(payload, dict):
        raise WorkbenchException(FUNDAMENTALS_ERROR, "pjm_load_areas.yaml must be a mapping")
    aliases: dict[str, str] = {}
    for area_id, record in payload.items():
        values = [str(area_id), *(str(value) for value in record.get("feed_values") or [])]
        for value in values:
            key = _compact_area(value)
            existing = aliases.get(key)
            if existing is not None and existing != area_id:
                raise WorkbenchException(FUNDAMENTALS_ERROR, f"PJM load area alias maps to multiple areas: {value}")
            aliases[key] = str(area_id)
    return aliases


def _compact_area(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def normalize_pjm_load_area(value: str, registry_dir: Path) -> str:
    aliases = load_pjm_load_area_aliases(registry_dir)
    key = _compact_area(value)
    if key not in aliases:
        raise WorkbenchException(UNKNOWN_PJM_LOAD_AREA, f"Unknown PJM load area: {value}")
    return aliases[key]


def _parse_utc(value: str, label: str) -> datetime:
    raw = str(value).strip()
    if not raw:
        raise WorkbenchException(FUNDAMENTALS_ERROR, f"{label} is required")
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        for fmt in ["%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y"]:
            try:
                parsed = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            raise WorkbenchException(FUNDAMENTALS_ERROR, f"{label} is not a recognized timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _first_value(row: dict[str, Any], columns: list[str], feed_id: str, label: str) -> Any:
    for column in columns:
        if column in row and row[column] not in {None, ""}:
            return row[column]
    raise WorkbenchException(FUNDAMENTALS_ERROR, f"{feed_id} missing {label}; expected one of {columns}")


def _metric_for_feed(feed: dict[str, Any]) -> str:
    metrics = list(feed.get("supported_metric_ids") or [])
    if not metrics:
        raise WorkbenchException(FUNDAMENTALS_ERROR, f"{feed.get('feed_id')} does not declare supported metrics")
    return str(metrics[0])


def normalize_pjm_fundamental_records(
    feed_id: str,
    rows: list[dict[str, Any]],
    registry_dir: Path,
    as_of: str | None = None,
) -> tuple[list[FundamentalObservation], list[ForecastSnapshot]]:
    feeds = load_pjm_fundamental_feeds(registry_dir)
    if feed_id not in feeds:
        raise WorkbenchException(FUNDAMENTALS_ERROR, f"Unknown PJM fundamental feed: {feed_id}")
    feed = dict(feeds[feed_id])
    feed["feed_id"] = feed_id
    time_columns = dict(feed["time_columns"])
    metric_id = _metric_for_feed(feed)
    observations: list[FundamentalObservation] = []
    forecasts: list[ForecastSnapshot] = []

    for row_number, row in enumerate(rows, start=1):
        start = _parse_utc(str(row[time_columns["delivery_start_utc"]]), "delivery_start")
        end_column = time_columns.get("delivery_end_utc")
        end = _parse_utc(str(row[end_column]), "delivery_end") if end_column and row.get(end_column) else start + timedelta(hours=1)
        if start >= end:
            raise WorkbenchException(FUNDAMENTALS_ERROR, "delivery_start must be before delivery_end")
        value = float(_first_value(row, list(feed["value_columns"]), feed_id, "value"))
        area_value = str(_first_value(row, list(feed["area_columns"]), feed_id, "area"))
        location_id = normalize_pjm_load_area(area_value, registry_dir)
        issued_column = time_columns.get("issued_at_utc")
        issued_at = _iso_z(_parse_utc(str(row[issued_column]), "issued_at")) if issued_column and row.get(issued_column) else as_of or _iso_z(end)
        lineage = {
            "source_name": "PJM Data Miner",
            "source_feed": feed_id,
            "raw_row_id": str(row_number),
            "raw_area": area_value,
            "quality": feed["feed_class"],
            "retention_product": feed["retention_product"],
        }
        if feed["feed_class"] in {"actual", "preliminary_actual"}:
            observations.append(
                FundamentalObservation(
                    as_of=issued_at,
                    source="PJM Data Miner",
                    metric=metric_id,
                    location_id=location_id,
                    delivery_start=_iso_z(start),
                    delivery_end=_iso_z(end),
                    value=value,
                    unit=str(feed["value_unit"]),
                    lineage=lineage,
                )
            )
        else:
            forecasts.append(
                ForecastSnapshot(
                    as_of=issued_at,
                    source="PJM Data Miner",
                    forecast_type=metric_id,
                    location_id=location_id,
                    delivery_start=_iso_z(start),
                    delivery_end=_iso_z(end),
                    value=value,
                    unit=str(feed["value_unit"]),
                    vintage=issued_at,
                    lineage=lineage,
                )
            )
    return observations, forecasts


def _record_key(record: FundamentalObservation | ForecastSnapshot) -> tuple[str, str, str]:
    return (record.location_id, record.delivery_start, record.delivery_end)


def _quality_rank(observation: FundamentalObservation) -> int:
    if observation.metric == "PJM.LOAD.ACTUAL.METERED.HOURLY_MW":
        return 100
    if observation.metric == "PJM.LOAD.ACTUAL.PRELIMINARY.HOURLY_MW":
        return 50
    return 0


def _group_by_metric(records: list[FundamentalObservation | ForecastSnapshot], attr: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        metric_id = str(getattr(record, attr))
        grouped.setdefault(metric_id, []).append(to_plain(record))
    return grouped


def _best_actuals(observations: list[FundamentalObservation]) -> list[dict[str, Any]]:
    best: dict[tuple[str, str, str], FundamentalObservation] = {}
    for observation in observations:
        key = _record_key(observation)
        current = best.get(key)
        if current is None or _quality_rank(observation) > _quality_rank(current):
            best[key] = observation
    records = []
    for observation in sorted(best.values(), key=lambda item: (item.location_id, item.delivery_start)):
        payload = to_plain(observation)
        payload["metric"] = BEST_ACTUAL_METRIC
        payload["lineage"] = {
            **payload.get("lineage", {}),
            "best_series_source_metric": observation.metric,
            "best_series_rule": "metered_preferred_over_preliminary",
        }
        records.append(payload)
    return records


def _latest_forecasts(forecasts: list[ForecastSnapshot]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str, str], ForecastSnapshot] = {}
    for forecast in forecasts:
        if forecast.forecast_type != "PJM.LOAD.FORECAST.SEVEN_DAY.LATEST.HOURLY_MW":
            continue
        key = _record_key(forecast)
        current = latest.get(key)
        if current is None or forecast.vintage > current.vintage:
            latest[key] = forecast
    return [to_plain(item) for item in sorted(latest.values(), key=lambda item: (item.location_id, item.delivery_start))]


def _forecast_errors(run_id: str, actuals: list[dict[str, Any]], forecasts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    forecast_by_key = {
        (item["location_id"], item["delivery_start"], item["delivery_end"]): item
        for item in forecasts
    }
    derived: list[dict[str, Any]] = []
    for actual in actuals:
        key = (actual["location_id"], actual["delivery_start"], actual["delivery_end"])
        forecast = forecast_by_key.get(key)
        if forecast is None:
            continue
        derived.append(
            {
                "as_of": actual["as_of"],
                "metric": SEVEN_DAY_ERROR_METRIC,
                "location_id": actual["location_id"],
                "delivery_start": actual["delivery_start"],
                "delivery_end": actual["delivery_end"],
                "value": float(actual["value"]) - float(forecast["value"]),
                "unit": "MW",
                "lineage": {
                    "calculation_run_id": run_id,
                    "formula": "actual_minus_forecast",
                    "input_metric_ids": [actual["metric"], forecast["forecast_type"]],
                },
            }
        )
    return derived


def _forecast_gaps(as_of: str, forecasts: list[dict[str, Any]], location_id: str = "PJM_RTO", days: int = 14) -> list[dict[str, Any]]:
    center = date.fromisoformat(as_of[:10])
    available_dates = {
        str(item["delivery_start"])[:10]
        for item in forecasts
        if item.get("location_id") == location_id
    }
    gaps: list[dict[str, Any]] = []
    for offset in range(0, days + 1):
        day = (center + timedelta(days=offset)).isoformat()
        if day not in available_dates:
            gaps.append(
                {
                    "metric_id": "PJM.LOAD.FORECAST.SEVEN_DAY.LATEST.HOURLY_MW",
                    "location_id": location_id,
                    "date": day,
                    "reason": "no_source_backed_forecast_for_day",
                    "horizon": f"+{offset}d",
                }
            )
    return gaps


def _records_on_date(records: list[dict[str, Any]], target_date: str) -> list[dict[str, Any]]:
    return [record for record in records if str(record.get("delivery_start", ""))[:10] == target_date]


def _sum_values(records: list[dict[str, Any]]) -> float | None:
    if not records:
        return None
    return float(sum(float(record["value"]) for record in records))


def _average_values(records: list[dict[str, Any]]) -> float | None:
    if not records:
        return None
    return _sum_values(records) / len(records)


def _coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"count": 0, "start": None, "end": None, "locations": []}
    return {
        "count": len(records),
        "start": min(str(record["delivery_start"]) for record in records),
        "end": max(str(record["delivery_end"]) for record in records),
        "locations": sorted({str(record["location_id"]) for record in records}),
    }


def _largest_abs(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    return max(records, key=lambda record: abs(float(record["value"])))


def _load_view_sections(state_payload: dict[str, Any]) -> dict[str, Any]:
    as_of = str(state_payload["as_of"])[:10]
    center = date.fromisoformat(as_of)
    prior_day = (center - timedelta(days=1)).isoformat()
    actuals = list(state_payload["best_series"][BEST_ACTUAL_METRIC])
    latest = list(state_payload["best_series"]["PJM.LOAD.FORECAST.SEVEN_DAY.LATEST.HOURLY_MW"])
    revisions = list(state_payload["best_series"]["PJM.LOAD.FORECAST.SEVEN_DAY.REVISION.HOURLY_MW"])
    diffs = list(state_payload["derived"])
    gaps = list(state_payload["gaps"])

    current_actuals = _records_on_date(actuals, as_of)
    current_forecasts = _records_on_date(latest, as_of)
    prior_actuals = _records_on_date(actuals, prior_day)
    prior_forecasts = _records_on_date(latest, prior_day)
    current_diffs = _records_on_date(diffs, as_of)
    prior_diffs = _records_on_date(diffs, prior_day)
    largest_error = _largest_abs(diffs)

    summary = (
        "PJM load fundamentals built from source-backed artifacts: "
        f"{len(actuals)} best actual intervals, {len(latest)} latest forecast intervals, "
        f"{len(revisions)} forecast revision intervals, {len(diffs)} actual-minus-forecast intervals, "
        f"and {len(gaps)} explicit forecast coverage gaps."
    )
    drivers = [
        {
            "name": "best_actual_load",
            "factor_class": "load",
            "direction": "available" if actuals else "missing",
            "value": _average_values(current_actuals),
            "unit": "MW",
            "record_count": len(actuals),
            "quality": "metered_preferred_over_preliminary",
        },
        {
            "name": "latest_load_forecast",
            "factor_class": "load",
            "direction": "available" if latest else "missing",
            "value": _average_values(current_forecasts),
            "unit": "MW",
            "record_count": len(latest),
            "coverage": _coverage(latest),
        },
        {
            "name": "forecast_error",
            "factor_class": "load",
            "direction": "actual_above_forecast" if largest_error and float(largest_error["value"]) > 0 else "actual_below_forecast" if largest_error else "missing",
            "value": float(largest_error["value"]) if largest_error else None,
            "unit": "MW",
            "record_count": len(diffs),
        },
        {
            "name": "forecast_coverage_gaps",
            "factor_class": "load",
            "direction": "gap" if gaps else "complete",
            "value": len(gaps),
            "unit": "days",
            "record_count": len(gaps),
        },
    ]
    driver_deltas = [
        {
            "name": "current_day_actual_minus_forecast_avg_mw",
            "value": _average_values(current_diffs),
            "unit": "MW",
            "record_count": len(current_diffs),
        },
        {
            "name": "prior_day_actual_minus_forecast_avg_mw",
            "value": _average_values(prior_diffs),
            "unit": "MW",
            "record_count": len(prior_diffs),
        },
    ]
    current_day_view = {
        "actual_load": {"records": current_actuals, "average_mw": _average_values(current_actuals), "total_mwh": _sum_values(current_actuals)},
        "load_forecast": {"records": current_forecasts, "average_mw": _average_values(current_forecasts), "total_mwh": _sum_values(current_forecasts)},
        "forecast_error": {"records": current_diffs, "average_mw": _average_values(current_diffs)},
    }
    prior_day_retrospective = {
        "actual_load": {"records": prior_actuals, "average_mw": _average_values(prior_actuals), "total_mwh": _sum_values(prior_actuals)},
        "load_forecast": {"records": prior_forecasts, "average_mw": _average_values(prior_forecasts), "total_mwh": _sum_values(prior_forecasts)},
        "forecast_error": {"records": prior_diffs, "average_mw": _average_values(prior_diffs), "largest_abs_error": largest_error},
    }
    fourteen_day_outlook = {
        "load_forecast": latest,
        "coverage": _coverage(latest),
        "gaps": gaps,
    }
    return {
        "summary": summary,
        "drivers": drivers,
        "driver_deltas": driver_deltas,
        "current_day_view": current_day_view,
        "prior_day_retrospective": prior_day_retrospective,
        "fourteen_day_outlook": fourteen_day_outlook,
    }


def build_pjm_load_fundamental_state(
    observations: list[FundamentalObservation],
    forecasts: list[ForecastSnapshot],
    as_of: str,
    run_id: str = "pjm-load-fundamentals",
) -> FundamentalState:
    actuals = _best_actuals(observations)
    latest = _latest_forecasts(forecasts)
    derived = _forecast_errors(run_id, actuals, latest)
    revisions = [to_plain(item) for item in forecasts if item.forecast_type == "PJM.LOAD.FORECAST.SEVEN_DAY.REVISION.HOURLY_MW"]
    return FundamentalState(
        run_id=run_id,
        as_of=as_of,
        source_products={
            **_group_by_metric(observations, "metric"),
            **_group_by_metric(forecasts, "forecast_type"),
        },
        best_series={
            BEST_ACTUAL_METRIC: actuals,
            "PJM.LOAD.FORECAST.SEVEN_DAY.LATEST.HOURLY_MW": latest,
            "PJM.LOAD.FORECAST.SEVEN_DAY.REVISION.HOURLY_MW": revisions,
        },
        derived=derived,
        gaps=_forecast_gaps(as_of, latest),
        lineage={
            "observation_count": len(observations),
            "forecast_count": len(forecasts),
            "best_actual_count": len(actuals),
            "latest_forecast_count": len(latest),
            "revision_count": len(revisions),
        },
    )


def build_pjm_load_artifacts(
    observations: list[FundamentalObservation],
    forecasts: list[ForecastSnapshot],
    as_of: str,
    run_id: str = "pjm-load-fundamentals",
) -> dict[str, Any]:
    state = build_pjm_load_fundamental_state(observations, forecasts, as_of, run_id=run_id)
    state_payload = to_plain(state)
    actuals = state_payload["best_series"][BEST_ACTUAL_METRIC]
    latest = state_payload["best_series"]["PJM.LOAD.FORECAST.SEVEN_DAY.LATEST.HOURLY_MW"]
    view_sections = _load_view_sections(state_payload)
    return {
        "pjm_load_fundamentals": state_payload,
        **view_sections,
        "inputs": {
            "actual_load": actuals,
            "load_forecast": latest,
        },
        "forecast_actual_diffs": state_payload["derived"],
        "source_lineage": [
            {
                "source": "PJM Data Miner",
                "artifact": "pjm_load_fundamentals",
                "run_id": run_id,
            }
        ],
    }


def validate_fundamental_state(state: FundamentalState | dict[str, Any], schema_dir: Path) -> None:
    schema = load_yaml_unique(Path(schema_dir) / "fundamental_state.schema.json")
    payload = to_plain(state)
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(FUNDAMENTALS_ERROR, f"fundamental state{suffix}: {first.message}")
