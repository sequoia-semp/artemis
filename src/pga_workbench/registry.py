from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from .exceptions import WorkbenchException

REGISTRY_VALIDATION_ERROR = "REGISTRY_VALIDATION_ERROR"
SYNTHETIC_PROMOTION_BLOCKED = "SYNTHETIC_PROMOTION_BLOCKED"
SHARED_READONLY_PUBLISH_BLOCKED = "SHARED_READONLY_PUBLISH_BLOCKED"


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise WorkbenchException(REGISTRY_VALIDATION_ERROR, f"Duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


@dataclass(frozen=True)
class RegistryValidationResult:
    registry_dir: str
    validated_files: list[str]
    checked_records: int
    warnings: list[str]


def load_yaml_unique(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=UniqueKeyLoader)


def _load_schema(schema_dir: Path, name: str) -> dict[str, Any]:
    return load_yaml_unique(schema_dir / name)


def _validate(schema: dict[str, Any], payload: dict[str, Any], label: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.path)
        suffix = f" at {path}" if path else ""
        raise WorkbenchException(REGISTRY_VALIDATION_ERROR, f"{label}{suffix}: {first.message}")


def _registry_record(key: str, value: dict[str, Any], id_field: str) -> dict[str, Any]:
    record = dict(value)
    record.setdefault(id_field, key)
    return record


def _validate_locations(data: dict[str, Any], schema: dict[str, Any], label: str) -> int:
    count = 0
    for location_id, value in data.items():
        _validate(schema, _registry_record(location_id, value, "location_id"), f"{label}:{location_id}")
        count += 1
    return count


def _validate_delivery_policies(data: dict[str, Any], schema: dict[str, Any]) -> int:
    count = 0
    for policy_id, value in data.items():
        _validate(schema, _registry_record(policy_id, value, "policy_id"), f"delivery_window_policies:{policy_id}")
        count += 1
    return count


def _validate_quoted_spreads(data: dict[str, Any], schema: dict[str, Any]) -> int:
    forbidden = set(data.get("FORBIDDEN_BY_DEFAULT", []))
    for label in forbidden:
        if label in data and isinstance(data[label], dict):
            raise WorkbenchException(REGISTRY_VALIDATION_ERROR, f"Forbidden spread orientation is registered as approved: {label}")
    count = 0
    for spread_id, value in data.items():
        if spread_id == "FORBIDDEN_BY_DEFAULT":
            continue
        record = dict(value)
        record.setdefault("spread_id", spread_id)
        record.setdefault("quote_label", spread_id)
        record.setdefault("first_index_id", record.get("first"))
        record.setdefault("second_index_id", record.get("second"))
        record.setdefault("quote_unit", "USD_per_MWh")
        _validate(schema, record, f"quoted_spreads:{spread_id}")
        if record.get("approved_orientation") is not True:
            raise WorkbenchException(REGISTRY_VALIDATION_ERROR, f"Spread must be explicitly approved: {spread_id}")
        count += 1
    return count


def _validate_gas_quantity_convention(data: dict[str, Any]) -> int:
    record = data.get("ICE_GAS_CONTRACT_0_25D_EQUIVALENT")
    if not isinstance(record, dict):
        raise WorkbenchException(REGISTRY_VALIDATION_ERROR, "Missing gas .25/d quantity convention")
    expected = {
        "d_per_contract": 0.25,
        "mmbtu_per_contract_per_day": 2500,
        "contracts_per_1d": 4,
        "mmbtu_per_1d_per_day": 10000,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise WorkbenchException(REGISTRY_VALIDATION_ERROR, f"Gas quantity convention changed: {key}={record.get(key)!r}")
    return len(data)


def _validate_mapping(data: dict[str, Any], schema: dict[str, Any], label: str) -> int:
    _validate(schema, data, label)
    return len(data)


def _validate_product_master(data: dict[str, Any], schema: dict[str, Any]) -> int:
    count = 0
    for product_id, value in data.items():
        _validate(schema, _registry_record(product_id, value, "product_id"), f"product_master:{product_id}")
        count += 1
    return count


def _validate_keyed_mapping(data: dict[str, Any], schema: dict[str, Any], label: str, id_field: str) -> int:
    count = 0
    for item_id, value in data.items():
        _validate(schema, _registry_record(item_id, value, id_field), f"{label}:{item_id}")
        count += 1
    return count


def _validate_vol_surface_universe(data: dict[str, Any], schema: dict[str, Any]) -> int:
    count = 0
    for universe_id, value in data.items():
        record = dict(value)
        if universe_id != "DEFAULT_FOR_OTHER_LOCATIONS":
            record.setdefault("location_id", universe_id)
        _validate(schema, record, f"vol_surface_universe:{universe_id}")
        count += 1
    return count


def validate_registries(registry_dir: Path, schema_dir: Path) -> RegistryValidationResult:
    registry_dir = Path(registry_dir)
    schema_dir = Path(schema_dir)
    validated_files: list[str] = []
    checked_records = 0
    warnings: list[str] = []

    file_handlers = {
        "power_locations.yaml": lambda data: _validate_locations(data, _load_schema(schema_dir, "location.schema.json"), "power_locations"),
        "gas_locations.yaml": lambda data: _validate_locations(data, _load_schema(schema_dir, "location.schema.json"), "gas_locations"),
        "delivery_window_policies.yaml": lambda data: _validate_delivery_policies(data, _load_schema(schema_dir, "delivery_window_policy.schema.json")),
        "market_indices.yaml": lambda data: _validate_mapping(data, _load_schema(schema_dir, "market_index_rules.schema.json"), "market_indices"),
        "period_aliases.yaml": lambda data: _validate_mapping(data, _load_schema(schema_dir, "period_aliases.schema.json"), "period_aliases"),
        "product_master.yaml": lambda data: _validate_product_master(data, _load_schema(schema_dir, "product_master_entry.schema.json")),
        "exchange_contracts.yaml": lambda data: _validate_keyed_mapping(data, _load_schema(schema_dir, "exchange_contract.schema.json"), "exchange_contracts", "contract_id"),
        "forward_fundamental_mappings.yaml": lambda data: _validate_keyed_mapping(data, _load_schema(schema_dir, "forward_fundamental_mapping.schema.json"), "forward_fundamental_mappings", "mapping_id"),
        "quoted_spreads.yaml": lambda data: _validate_quoted_spreads(data, _load_schema(schema_dir, "quoted_spread.schema.json")),
        "quantity_conventions.yaml": _validate_gas_quantity_convention,
        "vol_surface_universe.yaml": lambda data: _validate_vol_surface_universe(data, _load_schema(schema_dir, "vol_surface_universe_entry.schema.json")),
        "tools.yaml": lambda data: _validate_mapping(data, _load_schema(schema_dir, "tool.schema.json"), "tools"),
        "tool_permissions.yaml": lambda data: _validate_mapping(data, _load_schema(schema_dir, "tool_permissions.schema.json"), "tool_permissions"),
        "data_sources.yaml": lambda data: _validate_mapping(data, _load_schema(schema_dir, "data_source.schema.json"), "data_sources"),
        "market_regions.yaml": lambda data: _validate_mapping(data, _load_schema(schema_dir, "market_region.schema.json"), "market_regions"),
    }

    for path in sorted(registry_dir.glob("*.yaml")):
        data = load_yaml_unique(path)
        validated_files.append(path.name)
        handler = file_handlers.get(path.name)
        if handler is None:
            warnings.append(f"No schema handler for {path.name}; loaded with duplicate-key validation only.")
            if isinstance(data, dict):
                checked_records += len(data)
            continue
        checked_records += handler(data)

    return RegistryValidationResult(str(registry_dir), validated_files, checked_records, warnings)
