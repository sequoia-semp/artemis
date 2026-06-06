from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.registry import load_yaml_unique, validate_registries
from pga_workbench.services.power_system_retention import (
    POWER_SYSTEM_RETENTION_ERROR,
    load_power_system_artifact_retention_policies,
    validate_power_system_artifact_retention_references,
)


ROOT = Path(__file__).resolve().parents[1]


def _copy_retention_registries(tmp_path: Path) -> Path:
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in [
        "power_system_artifact_products.yaml",
        "power_system_artifact_retention_policies.yaml",
        "power_system_operators.yaml",
        "power_system_source_query_plans.yaml",
    ]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")
    return registry_dir


def test_power_system_artifact_retention_registry_validates_without_warnings():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")
    policies = load_power_system_artifact_retention_policies(ROOT / "registries")
    references = validate_power_system_artifact_retention_references(ROOT / "registries")

    assert "power_system_artifact_retention_policies.yaml" in result.validated_files
    assert result.warnings == []
    assert set(policies) == set(references["covered_artifact_products"])
    assert "pjm_load_fundamentals" in references["state_pack_publish_allowed"]
    assert references["historical_source_policies"]["pjm_power_prices"]["derived_view_windows_days"] == [1, 5, 10, 30]
    assert references["historical_source_policies"]["pjm_power_prices"]["approved_query_plan_ids"] == [
        "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS"
    ]
    assert policies["power_system_operational_event_feeds"]["state_pack_publish_allowed"] is False


def test_retention_policy_must_cover_every_artifact_product(tmp_path):
    registry_dir = _copy_retention_registries(tmp_path)
    policies = load_yaml_unique(registry_dir / "power_system_artifact_retention_policies.yaml")
    policies.pop("pjm_generation_mix")
    (registry_dir / "power_system_artifact_retention_policies.yaml").write_text(yaml.safe_dump(policies, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_retention_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_RETENTION_ERROR
    assert "missing retention policies" in exc.value.message
    assert "pjm_generation_mix" in exc.value.message


def test_retention_policy_unknown_artifact_product_fails_closed(tmp_path):
    registry_dir = _copy_retention_registries(tmp_path)
    policies = load_yaml_unique(registry_dir / "power_system_artifact_retention_policies.yaml")
    policies["unknown_power_artifact"] = dict(policies["pjm_power_prices"])
    (registry_dir / "power_system_artifact_retention_policies.yaml").write_text(yaml.safe_dump(policies, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_retention_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_RETENTION_ERROR
    assert "unknown artifact products" in exc.value.message
    assert "unknown_power_artifact" in exc.value.message


def test_candidate_retention_policy_cannot_allow_state_pack_publish(tmp_path):
    registry_dir = _copy_retention_registries(tmp_path)
    policies = load_yaml_unique(registry_dir / "power_system_artifact_retention_policies.yaml")
    policies["power_system_operational_event_feeds"]["state_pack_publish_allowed"] = True
    (registry_dir / "power_system_artifact_retention_policies.yaml").write_text(yaml.safe_dump(policies, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_retention_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_RETENTION_ERROR
    assert "state_pack_publish_allowed" in exc.value.message


def test_publishable_retention_policy_requires_lineage(tmp_path):
    registry_dir = _copy_retention_registries(tmp_path)
    policies = load_yaml_unique(registry_dir / "power_system_artifact_retention_policies.yaml")
    policies["pjm_power_prices"]["lineage_required"] = False
    (registry_dir / "power_system_artifact_retention_policies.yaml").write_text(yaml.safe_dump(policies, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_retention_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_RETENTION_ERROR
    assert "must require lineage" in exc.value.message
    assert "pjm_power_prices" in exc.value.message


def test_pjm_load_retention_keeps_latest_curve_and_revision_history_separate(tmp_path):
    registry_dir = _copy_retention_registries(tmp_path)
    policies = load_yaml_unique(registry_dir / "power_system_artifact_retention_policies.yaml")
    policies["pjm_load_fundamentals"]["forecast_revision_policy"] = "not_applicable"
    (registry_dir / "power_system_artifact_retention_policies.yaml").write_text(yaml.safe_dump(policies, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_retention_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_RETENTION_ERROR
    assert "latest forecast curves and revision history separate" in exc.value.message


def test_pjm_power_price_retention_keeps_heatmap_history_and_query_plan(tmp_path):
    registry_dir = _copy_retention_registries(tmp_path)
    policies = load_yaml_unique(registry_dir / "power_system_artifact_retention_policies.yaml")
    policies["pjm_power_prices"]["historical_source_policy"]["derived_view_windows_days"] = [1, 5, 10]
    (registry_dir / "power_system_artifact_retention_policies.yaml").write_text(yaml.safe_dump(policies, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_retention_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_RETENTION_ERROR
    assert "1d, 5d, 10d, and 30d" in exc.value.message


def test_source_restorable_retention_requires_known_query_plan(tmp_path):
    registry_dir = _copy_retention_registries(tmp_path)
    policies = load_yaml_unique(registry_dir / "power_system_artifact_retention_policies.yaml")
    policies["pjm_power_prices"]["historical_source_policy"]["approved_query_plan_ids"] = ["PJM_UNKNOWN_QUERY_PLAN"]
    (registry_dir / "power_system_artifact_retention_policies.yaml").write_text(yaml.safe_dump(policies, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_retention_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_RETENTION_ERROR
    assert "unknown query plans" in exc.value.message


def test_derived_view_window_cannot_exceed_hot_history_horizon(tmp_path):
    registry_dir = _copy_retention_registries(tmp_path)
    policies = load_yaml_unique(registry_dir / "power_system_artifact_retention_policies.yaml")
    policies["power_price_shape_rollups"]["historical_source_policy"]["derived_view_windows_days"] = [1, 5, 31]
    (registry_dir / "power_system_artifact_retention_policies.yaml").write_text(yaml.safe_dump(policies, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_retention_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_RETENTION_ERROR
    assert "derived view windows exceed max_hot_history_days" in exc.value.message
