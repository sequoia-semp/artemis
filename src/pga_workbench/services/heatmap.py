from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..exceptions import WorkbenchException
from ..models import ForwardPriceHeatmapReport, PriceSurfacePoint
from ..registry import load_yaml_unique
from ..serialization import read_json
from .power_system_retention import validate_power_system_artifact_retention_references

HEATMAP_ERROR = "HEATMAP_ERROR"


def _parse_as_of(value: str) -> datetime:
    raw = value.strip()
    if len(raw) == 10:
        raw = f"{raw}T23:59:59Z"
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_at_or_before(points: list[PriceSurfacePoint], target: datetime) -> PriceSurfacePoint | None:
    eligible = [point for point in points if _parse_as_of(point.as_of) <= target]
    if not eligible:
        return None
    return max(eligible, key=lambda point: _parse_as_of(point.as_of))


def _group_points(points: list[PriceSurfacePoint]) -> dict[tuple[str, str], list[PriceSurfacePoint]]:
    grouped: dict[tuple[str, str], list[PriceSurfacePoint]] = {}
    for point in points:
        grouped.setdefault((point.index_id, point.period_id), []).append(point)
    return grouped


def build_forward_price_heatmap(
    points: list[PriceSurfacePoint],
    as_of: str,
    run_id: str = "forward-price-heatmap",
    history_days: list[int] | None = None,
    registry_dir: Path | None = None,
    source_artifact_key: str = "pjm_power_prices",
) -> ForwardPriceHeatmapReport:
    history_days = history_days or _history_days_from_retention_policy(registry_dir, source_artifact_key) or [1, 5, 10, 30]
    target = _parse_as_of(as_of)
    cells: list[dict[str, Any]] = []

    for (index_id, period_id), series in sorted(_group_points(points).items()):
        current = _latest_at_or_before(series, target)
        if current is None:
            continue
        history: dict[str, Any] = {}
        for days in history_days:
            prior = _latest_at_or_before(series, target - timedelta(days=days))
            history[f"{days}d"] = {
                "as_of": prior.as_of if prior else None,
                "price": prior.price if prior else None,
                "delta": current.price - prior.price if prior else None,
            }
        cells.append(
            {
                "index_id": index_id,
                "period_id": period_id,
                "location_id": current.location_id,
                "commodity": current.commodity,
                "quote_unit": current.quote_unit,
                "current_as_of": current.as_of,
                "current_price": current.price,
                "history": history,
                "source": current.source,
                "source_role": current.source_role,
            }
        )

    return ForwardPriceHeatmapReport(
        run_id=run_id,
        as_of=target.isoformat().replace("+00:00", "Z"),
        history_days=history_days,
        cells=cells,
        lineage={"point_count": len(points), "group_count": len(cells)},
    )


def _history_days_from_retention_policy(registry_dir: Path | None, artifact_key: str) -> list[int]:
    if registry_dir is None:
        return []
    references = validate_power_system_artifact_retention_references(Path(registry_dir))
    policies = dict(references.get("historical_source_policies") or {})
    policy = dict(policies.get(artifact_key) or {})
    return [int(item) for item in policy.get("derived_view_windows_days") or []]


def read_price_surface_points(path: Path) -> list[PriceSurfacePoint]:
    return [PriceSurfacePoint(**item) for item in read_json(Path(path))]


def validate_forward_price_heatmap(report: ForwardPriceHeatmapReport, schema_dir: Path) -> None:
    schema = load_yaml_unique(Path(schema_dir) / "forward_price_heatmap.schema.json")
    from ..serialization import to_plain

    errors = sorted(Draft202012Validator(schema).iter_errors(to_plain(report)), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(HEATMAP_ERROR, f"forward price heatmap{suffix}: {first.message}")
