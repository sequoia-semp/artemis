from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from pga_workbench.analyst.view_engine import build_view, merge_hot_state_artifacts
from pga_workbench.cache.hot_state import HotState
from pga_workbench.cli import artemis_main, main
from pga_workbench.models import PriceSurfacePoint, RunManifest
from pga_workbench.registry import load_yaml_unique, validate_registries
from pga_workbench.serialization import read_json, write_json
from pga_workbench.services.power_price_shapes import (
    build_power_price_shape_artifacts,
    is_nerc_holiday,
    rollup_hourly_prices_to_daily_shapes,
    validate_power_price_shape_state,
)
from pga_workbench.state.packs import build_candidate_state_pack, publish_candidate_state_pack


ROOT = Path(__file__).resolve().parents[1]


def _hourly_points(day: str = "2026-06-01", count: int = 24) -> list[PriceSurfacePoint]:
    points: list[PriceSurfacePoint] = []
    base = datetime.fromisoformat(day + "T00:00:00")
    for hour in range(count):
        start = base + timedelta(hours=hour)
        end = start + timedelta(hours=1)
        hour_ending = 24 if hour == 23 else hour + 1
        period_id = f"HOUR_{start:%Y%m%dT%H%M%SZ}"
        points.append(
            PriceSurfacePoint(
                as_of=f"{day}T12:00:00Z",
                index_id=f"PJM.WH.RT.FULL_LMP.HOURLY.{period_id}",
                location_id="WH",
                commodity="power",
                period_id=period_id,
                price=float(hour_ending),
                quote_unit="USD_per_MWh",
                source="PJM Data Miner",
                source_role="authoritative_iso_publication",
                lineage={
                    "delivery_start_ept": start.isoformat(),
                    "delivery_start": start.isoformat() + "Z",
                    "delivery_end": end.isoformat() + "Z",
                    "price_component": "FULL_LMP",
                    "market_run": "RT",
                    "pnode_id": 51288,
                },
            )
        )
    return points


def test_power_price_shape_rule_registry_validates():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")
    rules = load_yaml_unique(ROOT / "registries" / "power_price_shape_rules.yaml")

    assert "power_price_shape_rules.yaml" in result.validated_files
    assert result.warnings == []
    assert set(rules) >= {
        "PJM_DAILY_PEAK_HE_0800_2300_EPT",
        "PJM_DAILY_OFFPEAK_5X8_2X24_EPT",
        "PJM_DAILY_ATC_24H_EPT",
    }


def test_daily_weekday_shape_rollups_use_registry_hours():
    state = rollup_hourly_prices_to_daily_shapes(_hourly_points(), ROOT / "registries", "2026-06-01", run_id="shape-test")

    validate_power_price_shape_state(state, ROOT / "schemas")
    by_shape = {item["lineage"]["shape"]: item for item in state.price_surface_points}
    assert by_shape["PEAK"]["index_id"] == "PJM.WH.RT.FULL_LMP.PEAK.DAY_20260601"
    assert by_shape["PEAK"]["price"] == 15.5
    assert by_shape["OFFPEAK"]["price"] == 6.5
    assert by_shape["ATC"]["price"] == 12.5
    assert by_shape["PEAK"]["lineage"]["input_hour_count"] == 16
    assert by_shape["OFFPEAK"]["lineage"]["input_hour_count"] == 8
    assert by_shape["ATC"]["lineage"]["input_hour_count"] == 24
    assert state.gaps == []


def test_incomplete_shape_day_emits_explicit_gaps_without_prices():
    offpeak_hours = {0, 1, 2, 3, 4, 5, 6, 23}
    source = [point for index, point in enumerate(_hourly_points()) if index in offpeak_hours]
    state = rollup_hourly_prices_to_daily_shapes(source, ROOT / "registries", "2026-06-01")

    assert len(state.price_surface_points) == 1
    assert state.price_surface_points[0]["lineage"]["shape"] == "OFFPEAK"
    gaps = {(gap["rule_id"], gap["observed_hours"], gap["expected_hours"]) for gap in state.gaps}
    assert ("PJM_DAILY_PEAK_HE_0800_2300_EPT", 0, 16) in gaps
    assert ("PJM_DAILY_ATC_24H_EPT", 8, 24) in gaps


def test_weekend_or_nerc_holiday_has_full_day_offpeak_and_no_peak_gap():
    assert is_nerc_holiday(date(2026, 7, 4))
    state = rollup_hourly_prices_to_daily_shapes(_hourly_points("2026-07-04"), ROOT / "registries", "2026-07-04")

    by_shape = {item["lineage"]["shape"]: item for item in state.price_surface_points}
    assert set(by_shape) == {"OFFPEAK", "ATC"}
    assert by_shape["OFFPEAK"]["lineage"]["input_hour_count"] == 24
    assert state.gaps == []


def test_power_price_shape_artifacts_publish_to_hot_state(tmp_path):
    artifacts = build_power_price_shape_artifacts(_hourly_points(), ROOT / "registries", "2026-06-01", run_id="shape-state")
    assert len(artifacts["price_surface_points"]) == 3
    assert artifacts["shape_gaps"] == []
    assert artifacts["summary"].startswith("Power price shape rollups built from source-backed hourly prices")
    assert artifacts["current_day_view"]["price_shapes"]["rollup_count"] == 3
    assert artifacts["drivers"][0]["name"] == "derived_price_shape_count"

    manifest = RunManifest(run_id="shape-state", created_at="2026-06-01T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "shape-state", "2026-06-01T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "shape-state")

    hot = HotState(tmp_path).artifacts()
    assert hot["power_price_shape_rollups"]["lineage"]["rollup_count"] == 3
    assert hot["price_surface_points"][0]["source_role"] == "derived_from_authoritative_iso_publication"
    assert hot["current_day_view"]["price_shapes"]["shape_prices"][0]["location_id"] == "WH"


def test_power_price_shape_hot_state_builds_current_day_view(tmp_path):
    artifacts = build_power_price_shape_artifacts(_hourly_points(), ROOT / "registries", "2026-06-01", run_id="shape-view")
    manifest = RunManifest(run_id="shape-view", created_at="2026-06-01T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "shape-view", "2026-06-01T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "shape-view")

    payload = merge_hot_state_artifacts(
        {"as_of": "2026-06-01", "data_environment": "development"},
        HotState(tmp_path).artifacts(),
    )
    view = build_view(ROOT, "current-day", payload)

    assert view["summary"].startswith("Power price shape rollups built from source-backed hourly prices")
    assert view["drivers"][0]["name"] == "derived_price_shape_count"
    assert view["current_day_view"]["price_shapes"]["rollup_count"] == 3
    assert {item["shape"] for item in view["current_day_view"]["price_shapes"]["shape_prices"]} == {"ATC", "OFFPEAK", "PEAK"}
    assert view["evidence"][0]["artifact"] == "power_price_shape_rollups"


def test_shape_rollups_ignore_lmp_component_points_until_component_rules_are_approved():
    source = _hourly_points()
    component_points = []
    for point in source:
        component_points.append(
            PriceSurfacePoint(
                as_of=point.as_of,
                index_id=point.index_id.replace(".FULL_LMP.", ".CONGESTION."),
                location_id=point.location_id,
                commodity=point.commodity,
                period_id=point.period_id,
                price=point.price - 1.0,
                quote_unit=point.quote_unit,
                source=point.source,
                source_role=point.source_role,
                lineage={**point.lineage, "price_component": "CONGESTION"},
            )
        )

    state = rollup_hourly_prices_to_daily_shapes(source + component_points, ROOT / "registries", "2026-06-01")

    assert len(state.price_surface_points) == 3
    assert state.lineage["source_point_count"] == 48
    assert state.lineage["eligible_full_lmp_source_point_count"] == 24
    assert {item["lineage"]["shape"] for item in state.price_surface_points} == {"PEAK", "OFFPEAK", "ATC"}


def test_power_price_shape_rollup_cli_builds_artifacts(tmp_path):
    source = tmp_path / "hourly_prices.json"
    output = tmp_path / "shape_prices.json"
    write_json(source, {"price_surface_points": _hourly_points()})

    assert main(
        [
            "rollup-power-price-shapes",
            "--input",
            str(source),
            "--as-of",
            "2026-06-01",
            "--output",
            str(output),
        ]
    ) == 0
    assert read_json(output)["power_price_shape_rollups"]["lineage"]["rollup_count"] == 3


def test_artemis_power_price_shape_rollup_cli_alias(tmp_path):
    source = tmp_path / "hourly_prices.json"
    output = tmp_path / "shape_prices.json"
    write_json(source, {"price_surface_points": _hourly_points()})

    assert artemis_main(
        [
            "analyst",
            "prices",
            "rollup-shapes",
            "--input",
            str(source),
            "--as-of",
            "2026-06-01",
            "--rule",
            "PJM_DAILY_PEAK_HE_0800_2300_EPT",
            "--output",
            str(output),
        ]
    ) == 0
    payload = read_json(output)
    assert len(payload["price_surface_points"]) == 1
    assert payload["price_surface_points"][0]["lineage"]["shape"] == "PEAK"
