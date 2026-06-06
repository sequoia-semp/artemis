from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..exceptions import WorkbenchException

ARTIFACT_COMPOSITION_ERROR = "ARTIFACT_COMPOSITION_ERROR"

LIST_CONCAT_KEYS = {
    "drivers",
    "driver_deltas",
    "forecast_actual_diffs",
    "evidence",
    "scenarios",
    "source_lineage",
    "price_surface_points",
    "generation_mix_observations",
    "raw_source_fetch_manifests",
    "shape_gaps",
}
DICT_MERGE_KEYS = {
    "inputs",
    "view_payload",
    "market_scope",
    "current_day_view",
    "prior_day_retrospective",
    "fourteen_day_outlook",
}
TEXT_JOIN_KEYS = {
    "summary",
    "stance_summary",
}
RESERVED_METADATA_KEY = "artifact_composition"
COMPOSITION_PRODUCT_KEYS = {
    "pjm_load_fundamentals",
    "pjm_power_prices",
    "power_price_shape_rollups",
    "pjm_generation_mix",
}
SOURCE_PRODUCT_KEYS = COMPOSITION_PRODUCT_KEYS
VIEW_FIELD_KEYS = {
    "summary",
    "stance_summary",
    "market_scope",
    "drivers",
    "driver_deltas",
    "forecast_actual_diffs",
    "evidence",
    "scenarios",
    "inputs",
    "current_day_view",
    "prior_day_retrospective",
    "fourteen_day_outlook",
}


def _join_text(left: Any, right: Any, path: str) -> str:
    values = []
    for value in [left, right]:
        text = str(value).strip()
        if text and text not in values:
            values.append(text)
    if not values:
        raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, f"Cannot compose empty text field at {path}")
    return "\n".join(values)


def _merge_lists(left: Any, right: Any, path: str) -> list[Any]:
    if not isinstance(left, list) or not isinstance(right, list):
        raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, f"Expected lists at {path}")
    return [*deepcopy(left), *deepcopy(right)]


def _merge_dicts(left: dict[str, Any], right: dict[str, Any], path: str) -> dict[str, Any]:
    merged = deepcopy(left)
    for key, value in right.items():
        child_path = f"{path}.{key}" if path else str(key)
        if key not in merged:
            merged[key] = deepcopy(value)
            continue
        merged[key] = _merge_value(key, merged[key], value, child_path)
    return merged


def _merge_market_scope(left: dict[str, Any], right: dict[str, Any], path: str) -> dict[str, Any]:
    merged = _merge_dicts(left, right, path)
    for key in ["regions", "exchange_scope"]:
        values: list[Any] = []
        for item in [*(left.get(key) or []), *(right.get(key) or [])]:
            if item not in values:
                values.append(item)
        if values:
            merged[key] = values
    return merged


def _merge_value(key: str, left: Any, right: Any, path: str) -> Any:
    if left == right:
        return deepcopy(left)
    if key in TEXT_JOIN_KEYS:
        return _join_text(left, right, path)
    if key in LIST_CONCAT_KEYS:
        return _merge_lists(left, right, path)
    if key == "market_scope":
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, f"Expected market_scope mappings at {path}")
        return _merge_market_scope(left, right, path)
    if key in DICT_MERGE_KEYS:
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, f"Expected mappings at {path}")
        return _merge_dicts(left, right, path)
    raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, f"Ambiguous artifact key collision at {path}")


def _payload_composition_product_keys(payload: dict[str, Any]) -> list[str]:
    return sorted(key for key in payload if key in COMPOSITION_PRODUCT_KEYS)


def _payload_view_fields(payload: dict[str, Any]) -> list[str]:
    return sorted(key for key in payload if key in VIEW_FIELD_KEYS)


def _composition_metadata(payloads: tuple[dict[str, Any], ...], composed: dict[str, Any]) -> dict[str, Any]:
    return {
        "payload_count": len(payloads),
        "composition_product_keys": sorted({key for payload in payloads for key in _payload_composition_product_keys(payload)}),
        "view_fields": sorted(key for key in composed if key in VIEW_FIELD_KEYS),
        "shared_list_counts": {
            key: len(composed[key])
            for key in sorted(LIST_CONCAT_KEYS)
            if isinstance(composed.get(key), list)
        },
        "input_keys": sorted(str(key) for key in composed.get("inputs", {}) if isinstance(composed.get("inputs"), dict)),
        "current_day_view_keys": sorted(str(key) for key in composed.get("current_day_view", {}) if isinstance(composed.get("current_day_view"), dict)),
        "payloads": [
            {
                "ordinal": index,
                "composition_product_keys": _payload_composition_product_keys(payload),
                "view_fields": _payload_view_fields(payload),
            }
            for index, payload in enumerate(payloads, start=1)
        ],
    }


def expected_artifact_composition_metadata(composed: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(composed, dict):
        raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, "Composed artifact payload must be a mapping")
    if RESERVED_METADATA_KEY not in composed:
        raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, "Composed artifact payload is missing artifact_composition metadata")
    metadata = composed.get(RESERVED_METADATA_KEY)
    if not isinstance(metadata, dict):
        raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, "artifact_composition metadata must be a mapping")
    payloads = metadata.get("payloads")
    if not isinstance(payloads, list):
        raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, "artifact_composition.payloads must be a list")
    return {
        "payload_count": len(payloads),
        "composition_product_keys": sorted(key for key in composed if key in COMPOSITION_PRODUCT_KEYS),
        "view_fields": sorted(key for key in composed if key in VIEW_FIELD_KEYS),
        "shared_list_counts": {
            key: len(composed[key])
            for key in sorted(LIST_CONCAT_KEYS)
            if isinstance(composed.get(key), list)
        },
        "input_keys": sorted(str(key) for key in composed.get("inputs", {}) if isinstance(composed.get("inputs"), dict)),
        "current_day_view_keys": sorted(str(key) for key in composed.get("current_day_view", {}) if isinstance(composed.get("current_day_view"), dict)),
    }


def validate_artifact_composition_metadata(composed: dict[str, Any]) -> None:
    metadata = composed.get(RESERVED_METADATA_KEY)
    expected = expected_artifact_composition_metadata(composed)
    for key, expected_value in expected.items():
        observed = metadata.get(key)
        if observed != expected_value:
            raise WorkbenchException(
                ARTIFACT_COMPOSITION_ERROR,
                f"artifact_composition.{key} does not match composed artifact payload",
            )
    if "source_product_keys" in metadata and metadata["source_product_keys"] != expected["composition_product_keys"]:
        raise WorkbenchException(
            ARTIFACT_COMPOSITION_ERROR,
            "artifact_composition.source_product_keys does not match composed artifact payload",
        )


def compose_artifact_payloads(*payloads: dict[str, Any]) -> dict[str, Any]:
    if not payloads:
        raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, "At least one artifact payload is required")
    composed: dict[str, Any] = {}
    for index, payload in enumerate(payloads, start=1):
        if not isinstance(payload, dict):
            raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, f"Artifact payload {index} must be a mapping")
        if RESERVED_METADATA_KEY in payload:
            raise WorkbenchException(ARTIFACT_COMPOSITION_ERROR, f"Artifact payload {index} uses reserved key: {RESERVED_METADATA_KEY}")
        composed = _merge_dicts(composed, payload, "")
    composed[RESERVED_METADATA_KEY] = _composition_metadata(payloads, composed)
    return composed
