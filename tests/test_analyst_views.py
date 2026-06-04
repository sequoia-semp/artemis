from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.analyst.view_engine import build_view
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.serialization import read_json


ROOT = Path(__file__).resolve().parents[1]


def test_current_day_view_builds_schema_valid_payload():
    view = build_view(ROOT, "current-day", read_json(ROOT / "tests/fixtures/views/current_day_minimal.json"))

    assert view["view_type"] == "current_day"
    assert view["horizon"]["start_date"] == "2026-06-04"
    assert view["missing_inputs"] == []
    assert view["data_quality"]["fixture_mode"] is False


def test_prior_day_and_fourteen_day_views_build():
    prior = build_view(ROOT, "prior-day-retrospective", read_json(ROOT / "tests/fixtures/views/prior_day_minimal.json"))
    fourteen = build_view(ROOT, "fourteen-day-fundamentals", read_json(ROOT / "tests/fixtures/views/fourteen_day_minimal.json"))
    delta = build_view(ROOT, "forecast-actual-delta", read_json(ROOT / "tests/fixtures/views/forecast_actual_delta_minimal.json"))

    assert prior["view_type"] == "prior_day_retrospective"
    assert prior["horizon"]["type"] == "prior_day"
    assert fourteen["horizon"]["start_date"] == "2026-05-21"
    assert fourteen["horizon"]["end_date"] == "2026-06-18"
    assert delta["view_type"] == "forecast_actual_delta"


def test_view_build_rejects_fixture_data_without_explicit_flag():
    with pytest.raises(WorkbenchException):
        build_view(ROOT, "current-day", read_json(ROOT / "tests/fixtures/views/fixture_data_minimal.json"))


def test_view_build_allows_fixture_data_when_explicit():
    view = build_view(ROOT, "current-day", read_json(ROOT / "tests/fixtures/views/fixture_data_minimal.json"), allow_fixture=True)

    assert view["data_quality"]["fixture_mode"] is True
