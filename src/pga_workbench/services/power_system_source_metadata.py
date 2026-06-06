from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from .fundamentals import load_pjm_fundamental_feeds
from .generation_mix import load_power_generation_mix_feeds
from .power_prices import load_power_system_price_feeds
from .power_system_sources import load_power_system_source_catalog

POWER_SYSTEM_SOURCE_METADATA_ERROR = "POWER_SYSTEM_SOURCE_METADATA_ERROR"


@dataclass(frozen=True)
class SourceMetadataExpectation:
    registry_feed_id: str
    data_miner_feed: str
    product_family: str
    registry_file: str
    required_fields: tuple[str, ...]
    status: str


def collect_pjm_data_miner_metadata_expectations(registry_dir: Path) -> dict[str, SourceMetadataExpectation]:
    registry_dir = Path(registry_dir)
    expectations: dict[str, SourceMetadataExpectation] = {}

    for feed_id, feed in load_pjm_fundamental_feeds(registry_dir).items():
        _add_expectation(
            expectations,
            registry_feed_id=feed_id,
            data_miner_feed=str(feed["data_miner_feed"]),
            product_family="load",
            registry_file="pjm_fundamental_feeds.yaml",
            required_fields=_fundamental_fields(feed),
            status=str(feed["status"]),
        )

    for feed_id, feed in load_power_system_price_feeds(registry_dir).items():
        _add_expectation(
            expectations,
            registry_feed_id=feed_id,
            data_miner_feed=str(feed["data_miner_feed"]),
            product_family=str(feed["product_type"]),
            registry_file="power_system_price_feeds.yaml",
            required_fields=_price_fields(feed),
            status=str(feed["status"]),
        )

    for feed_id, feed in load_power_generation_mix_feeds(registry_dir).items():
        _add_expectation(
            expectations,
            registry_feed_id=feed_id,
            data_miner_feed=str(feed["data_miner_feed"]),
            product_family="generation_mix",
            registry_file="power_generation_mix_feeds.yaml",
            required_fields=_generation_mix_fields(feed),
            status=str(feed["status"]),
        )

    return expectations


def validate_power_system_source_metadata_references(registry_dir: Path) -> dict[str, Any]:
    expectations = collect_pjm_data_miner_metadata_expectations(registry_dir)
    catalog = load_power_system_source_catalog(registry_dir)
    catalog_feed_ids = {
        str(feed_id)
        for record in catalog.values()
        if record.get("status") == "approved_core"
        for feed_id in record.get("registry_feed_ids") or []
    }
    missing = sorted(catalog_feed_ids - {item.registry_feed_id for item in expectations.values()})
    if missing:
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_METADATA_ERROR,
            f"Approved source publications reference feeds without metadata expectations: {', '.join(missing)}",
        )
    empty = sorted(item.registry_feed_id for item in expectations.values() if not item.required_fields)
    if empty:
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_METADATA_ERROR,
            f"Metadata expectations must declare required fields: {', '.join(empty)}",
        )
    return {
        "metadata_expectation_count": len(expectations),
        "approved_catalog_feed_ids": sorted(catalog_feed_ids),
        "data_miner_feeds": sorted(expectations),
    }


def select_pjm_data_miner_metadata_expectations(
    registry_dir: Path,
    feeds: list[str] | None = None,
    include_candidate: bool = False,
) -> dict[str, SourceMetadataExpectation]:
    expectations = collect_pjm_data_miner_metadata_expectations(registry_dir)
    if feeds:
        selected: dict[str, SourceMetadataExpectation] = {}
        by_registry_id = {item.registry_feed_id: item for item in expectations.values()}
        for feed in feeds:
            expectation = expectations.get(feed) or by_registry_id.get(feed)
            if expectation is None:
                raise WorkbenchException(POWER_SYSTEM_SOURCE_METADATA_ERROR, f"Unknown PJM Data Miner metadata feed selection: {feed}")
            selected[expectation.data_miner_feed] = expectation
        return selected
    if include_candidate:
        return expectations
    return {feed: expectation for feed, expectation in expectations.items() if expectation.status == "approved_core"}


def verify_pjm_data_miner_definitions(
    definition_payloads: dict[str, dict[str, Any]],
    registry_dir: Path,
    feeds: list[str] | None = None,
    include_candidate: bool = False,
) -> dict[str, Any]:
    selected = select_pjm_data_miner_metadata_expectations(registry_dir, feeds=feeds, include_candidate=include_candidate)
    missing_payloads = sorted(set(selected) - set(definition_payloads))
    if missing_payloads:
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_METADATA_ERROR,
            f"Missing PJM Data Miner definition payloads: {', '.join(missing_payloads)}",
        )
    verified = [
        verify_pjm_data_miner_definition(feed, definition_payloads[feed], registry_dir)
        for feed in sorted(selected)
    ]
    return {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "verified_feed_count": len(verified),
        "verified_feeds": verified,
        "include_candidate": include_candidate,
    }


def verify_pjm_data_miner_definition(
    data_miner_feed: str,
    definition_payload: dict[str, Any],
    registry_dir: Path,
) -> dict[str, Any]:
    expectations = collect_pjm_data_miner_metadata_expectations(registry_dir)
    expectation = expectations.get(data_miner_feed)
    if expectation is None:
        raise WorkbenchException(POWER_SYSTEM_SOURCE_METADATA_ERROR, f"Unknown PJM Data Miner feed for metadata verification: {data_miner_feed}")
    observed_fields = extract_definition_fields(definition_payload)
    missing = sorted(set(expectation.required_fields) - observed_fields)
    if missing:
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_METADATA_ERROR,
            f"{data_miner_feed} definition is missing required registry fields: {', '.join(missing)}",
        )
    return {
        "registry_feed_id": expectation.registry_feed_id,
        "data_miner_feed": data_miner_feed,
        "required_field_count": len(expectation.required_fields),
        "observed_field_count": len(observed_fields),
        "missing_fields": [],
    }


def extract_definition_fields(payload: dict[str, Any]) -> set[str]:
    fields: set[str] = set()
    _collect_definition_fields(payload, fields)
    return fields


def _add_expectation(
    expectations: dict[str, SourceMetadataExpectation],
    *,
    registry_feed_id: str,
    data_miner_feed: str,
    product_family: str,
    registry_file: str,
    required_fields: set[str],
    status: str,
) -> None:
    existing = expectations.get(data_miner_feed)
    if existing is not None:
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_METADATA_ERROR,
            f"Multiple registry feed descriptors reference one Data Miner feed: {data_miner_feed}",
        )
    expectations[data_miner_feed] = SourceMetadataExpectation(
        registry_feed_id=registry_feed_id,
        data_miner_feed=data_miner_feed,
        product_family=product_family,
        registry_file=registry_file,
        required_fields=tuple(sorted(required_fields)),
        status=status,
    )


def _non_empty(values: Any) -> set[str]:
    fields: set[str] = set()
    if isinstance(values, dict):
        for value in values.values():
            fields.update(_non_empty(value))
    elif isinstance(values, list):
        for value in values:
            fields.update(_non_empty(value))
    elif values not in {None, ""}:
        fields.add(str(values))
    return fields


def _fundamental_fields(feed: dict[str, Any]) -> set[str]:
    fields = set()
    for key in ["time_columns", "value_columns", "area_columns"]:
        fields.update(_non_empty(feed.get(key)))
    return fields


def _price_fields(feed: dict[str, Any]) -> set[str]:
    fields = set()
    for key in ["time_columns", "pnode_columns", "value_columns", "version_columns"]:
        fields.update(_non_empty(feed.get(key)))
    fields.update(str(key) for key in dict(feed.get("required_filters") or {}))
    return fields


def _generation_mix_fields(feed: dict[str, Any]) -> set[str]:
    fields = set()
    for key in ["time_columns", "fuel_columns", "value_columns"]:
        fields.update(_non_empty(feed.get(key)))
    return fields


def _collect_definition_fields(value: Any, fields: set[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_definition_fields(item, fields)
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        key_label = str(key).lower()
        if key_label in {"name", "field", "fieldname", "field_name", "attribute", "attribute_name", "column", "column_name"}:
            if item not in {None, ""}:
                fields.add(str(item))
        if isinstance(item, (dict, list)):
            _collect_definition_fields(item, fields)
