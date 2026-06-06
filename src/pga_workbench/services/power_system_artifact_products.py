from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from .artifact_composition import COMPOSITION_PRODUCT_KEYS
from .power_system_operators import load_power_system_operators

POWER_SYSTEM_ARTIFACT_PRODUCT_ERROR = "POWER_SYSTEM_ARTIFACT_PRODUCT_ERROR"


def load_power_system_artifact_products(registry_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_yaml_unique(Path(registry_dir) / "power_system_artifact_products.yaml")
    if not isinstance(data, dict):
        raise WorkbenchException(POWER_SYSTEM_ARTIFACT_PRODUCT_ERROR, "power_system_artifact_products.yaml must be a mapping")
    return {str(key): dict(value) for key, value in data.items() if isinstance(value, dict)}


def composition_product_keys_from_registry(registry_dir: Path) -> set[str]:
    products = load_power_system_artifact_products(registry_dir)
    return {key for key, record in products.items() if record.get("composition_product_key") is True}


def validate_power_system_artifact_product_references(registry_dir: Path) -> dict[str, Any]:
    products = load_power_system_artifact_products(registry_dir)
    operators = load_power_system_operators(registry_dir)
    missing_operators = sorted({str(record.get("operator_id")) for record in products.values()} - set(operators))
    if missing_operators:
        raise WorkbenchException(
            POWER_SYSTEM_ARTIFACT_PRODUCT_ERROR,
            f"Artifact products reference unknown operators: {', '.join(missing_operators)}",
        )
    composition_keys = composition_product_keys_from_registry(registry_dir)
    if composition_keys != COMPOSITION_PRODUCT_KEYS:
        raise WorkbenchException(
            POWER_SYSTEM_ARTIFACT_PRODUCT_ERROR,
            "Artifact product composition keys do not match artifact composition service keys",
        )
    candidate_publish = [
        key
        for key, record in products.items()
        if record.get("status") == "candidate" and record.get("state_pack_publish_status") == "approved_core"
    ]
    if candidate_publish:
        raise WorkbenchException(
            POWER_SYSTEM_ARTIFACT_PRODUCT_ERROR,
            f"Candidate artifact products cannot be approved for state-pack publish: {', '.join(sorted(candidate_publish))}",
        )
    return {
        "artifact_product_count": len(products),
        "composition_product_keys": sorted(composition_keys),
    }


def validate_state_pack_artifact_product_publish_status(artifacts: dict[str, Any], registry_dir: Path) -> None:
    products = load_power_system_artifact_products(registry_dir)
    blocked = []
    for artifact_key in artifacts:
        product = products.get(str(artifact_key))
        if product is None:
            continue
        if product.get("state_pack_publish_status") != "approved_core":
            blocked.append(str(artifact_key))
    if blocked:
        raise WorkbenchException(
            POWER_SYSTEM_ARTIFACT_PRODUCT_ERROR,
            f"Artifact products are not approved for state-pack publish: {', '.join(sorted(blocked))}",
        )
