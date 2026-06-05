from __future__ import annotations

from pathlib import Path

from pga_workbench.registry import load_yaml_unique, validate_registries


ROOT = Path(__file__).resolve().parents[1]


def test_fundamental_metric_registry_validates_without_warnings():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")

    assert "fundamental_metrics.yaml" in result.validated_files
    assert result.warnings == []


def test_initial_pjm_fundamental_metric_classes_are_registered():
    metrics = load_yaml_unique(ROOT / "registries" / "fundamental_metrics.yaml")

    assert set(metrics) >= {
        "PJM.LOAD.ACTUAL.HOURLY_MW",
        "PJM.LOAD.FORECAST.DAY_AHEAD.HOURLY_MW",
        "PJM.LOAD.FORECAST_ERROR.DAY_AHEAD.HOURLY_MW",
    }
    assert {record["metric_class"] for record in metrics.values()} >= {"actual", "forecast", "derived"}
    assert metrics["PJM.LOAD.FORECAST.DAY_AHEAD.HOURLY_MW"]["forecast"]["vintage_policy"] == "latest_curve"
    assert metrics["PJM.LOAD.FORECAST_ERROR.DAY_AHEAD.HOURLY_MW"]["formula"] == {
        "formula_type": "ACTUAL_MINUS_FORECAST",
        "input_metric_ids": [
            "PJM.LOAD.ACTUAL.HOURLY_MW",
            "PJM.LOAD.FORECAST.DAY_AHEAD.HOURLY_MW",
        ],
    }


def test_fundamental_metric_registry_does_not_introduce_live_api_requirements():
    metrics = load_yaml_unique(ROOT / "registries" / "fundamental_metrics.yaml")

    assert all(record["source_status"] == "registry_only" for record in metrics.values())
