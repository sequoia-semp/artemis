from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.registry import load_yaml_unique, validate_registries
from pga_workbench.services.artifact_composition import COMPOSITION_PRODUCT_KEYS
from pga_workbench.services.power_system_artifact_products import (
    POWER_SYSTEM_ARTIFACT_PRODUCT_ERROR,
    composition_product_keys_from_registry,
    load_power_system_artifact_products,
    validate_state_pack_artifact_product_publish_status,
    validate_power_system_artifact_product_references,
)


ROOT = Path(__file__).resolve().parents[1]


def test_power_system_artifact_product_registry_validates_without_warnings():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")
    products = load_power_system_artifact_products(ROOT / "registries")

    assert "power_system_artifact_products.yaml" in result.validated_files
    assert result.warnings == []
    assert products["pjm_load_fundamentals"]["artifact_role"] == "source_product"
    assert products["power_price_shape_rollups"]["artifact_role"] == "derived_product"
    assert products["power_system_operational_event_feeds"]["state_pack_publish_status"] == "candidate_only"


def test_artifact_product_composition_keys_match_composer():
    result = validate_power_system_artifact_product_references(ROOT / "registries")

    assert set(result["composition_product_keys"]) == COMPOSITION_PRODUCT_KEYS
    assert composition_product_keys_from_registry(ROOT / "registries") == COMPOSITION_PRODUCT_KEYS


def test_artifact_product_unknown_operator_fails_closed(tmp_path):
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in ["power_system_artifact_products.yaml", "power_system_operators.yaml"]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")

    products = load_yaml_unique(registry_dir / "power_system_artifact_products.yaml")
    products["pjm_load_fundamentals"]["operator_id"] = "UNKNOWN_OPERATOR"
    (registry_dir / "power_system_artifact_products.yaml").write_text(yaml.safe_dump(products, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_product_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_ARTIFACT_PRODUCT_ERROR
    assert "UNKNOWN_OPERATOR" in exc.value.message


def test_candidate_artifact_product_cannot_be_approved_for_publish(tmp_path):
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in ["power_system_artifact_products.yaml", "power_system_operators.yaml"]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")

    products = load_yaml_unique(registry_dir / "power_system_artifact_products.yaml")
    products["power_system_operational_event_feeds"]["state_pack_publish_status"] = "approved_core"
    (registry_dir / "power_system_artifact_products.yaml").write_text(yaml.safe_dump(products, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_artifact_product_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_ARTIFACT_PRODUCT_ERROR
    assert "Candidate artifact products cannot be approved" in exc.value.message


def test_state_pack_artifact_product_publish_status_blocks_candidate_products():
    with pytest.raises(WorkbenchException) as exc:
        validate_state_pack_artifact_product_publish_status(
            {"power_system_operational_event_feeds": {}},
            ROOT / "registries",
        )

    assert exc.value.code == POWER_SYSTEM_ARTIFACT_PRODUCT_ERROR
    assert "not approved for state-pack publish" in exc.value.message


def test_state_pack_artifact_product_publish_status_allows_unregistered_legacy_keys():
    validate_state_pack_artifact_product_publish_status({"prices": [{"value": 1}]}, ROOT / "registries")
