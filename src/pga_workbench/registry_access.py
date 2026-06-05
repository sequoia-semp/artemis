from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from typing import Any

from .exceptions import WorkbenchException, UNKNOWN_GAS_LOCATION, UNKNOWN_PRODUCT
from .registry import REGISTRY_VALIDATION_ERROR, load_yaml_unique


DEFAULT_REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registries"


@dataclass(frozen=True)
class RegistryCatalog:
    registry_dir: Path
    market_rules: dict[str, Any]
    power_locations: dict[str, dict[str, Any]]
    gas_locations: dict[str, dict[str, Any]]
    gas_aliases: dict[str, str]
    approved_spreads: dict[str, dict[str, Any]]
    forbidden_spreads: frozenset[str]
    exchange_contracts: dict[str, dict[str, Any]]
    option_contracts: dict[str, dict[str, Any]]
    forward_fundamental_mappings: dict[str, dict[str, Any]]


def compact_label(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _read_mapping(registry_dir: Path, name: str) -> dict[str, Any]:
    data = load_yaml_unique(registry_dir / name)
    if not isinstance(data, dict):
        raise WorkbenchException(REGISTRY_VALIDATION_ERROR, f"{name} must be a mapping")
    return data


def _build_gas_aliases(gas_locations: dict[str, dict[str, Any]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for location_id, record in gas_locations.items():
        values = [location_id, str(record.get("display_name") or "")]
        values.extend(str(alias) for alias in record.get("aliases") or [])
        for value in values:
            compact = compact_label(value)
            if not compact:
                continue
            existing = aliases.get(compact)
            if existing is not None and existing != location_id:
                raise WorkbenchException(REGISTRY_VALIDATION_ERROR, f"Gas alias maps to multiple locations: {value}")
            aliases[compact] = location_id
    return aliases


@lru_cache(maxsize=16)
def load_registry_catalog(registry_dir: str | Path = DEFAULT_REGISTRY_DIR) -> RegistryCatalog:
    root = Path(registry_dir)
    market_indices = _read_mapping(root, "market_indices.yaml")
    power_locations = _read_mapping(root, "power_locations.yaml")
    gas_locations = _read_mapping(root, "gas_locations.yaml")
    quoted_spreads = _read_mapping(root, "quoted_spreads.yaml")
    exchange_contracts = _read_mapping(root, "exchange_contracts.yaml")
    option_contracts = _read_mapping(root, "option_contracts.yaml")
    forward_fundamental_mappings = _read_mapping(root, "forward_fundamental_mappings.yaml")

    forbidden = frozenset(str(item).strip().upper().replace(" ", "") for item in quoted_spreads.get("FORBIDDEN_BY_DEFAULT", []))
    approved = {
        str(spread_id).strip().upper().replace(" ", ""): dict(record)
        for spread_id, record in quoted_spreads.items()
        if spread_id != "FORBIDDEN_BY_DEFAULT" and isinstance(record, dict)
    }
    return RegistryCatalog(
        registry_dir=root,
        market_rules=dict(market_indices.get("rules") or {}),
        power_locations={str(key).upper(): dict(value) for key, value in power_locations.items()},
        gas_locations={str(key).upper(): dict(value) for key, value in gas_locations.items()},
        gas_aliases=_build_gas_aliases({str(key).upper(): dict(value) for key, value in gas_locations.items()}),
        approved_spreads=approved,
        forbidden_spreads=forbidden,
        exchange_contracts={str(key).upper(): dict(value) for key, value in exchange_contracts.items()},
        option_contracts={str(key).upper(): dict(value) for key, value in option_contracts.items()},
        forward_fundamental_mappings={str(key).upper(): dict(value) for key, value in forward_fundamental_mappings.items()},
    )


def find_power_location(raw: str, catalog: RegistryCatalog | None = None) -> str:
    catalog = catalog or load_registry_catalog()
    tokens = re.split(r"\s+", raw.strip().upper().replace("-", " "))
    location = next((token for token in tokens if token in catalog.power_locations), None)
    if location is None:
        raise WorkbenchException(UNKNOWN_PRODUCT, f"Unknown power location in {raw}")
    return location


def find_gas_location(raw: str, catalog: RegistryCatalog | None = None) -> str:
    catalog = catalog or load_registry_catalog()
    compact = compact_label(raw)
    matches = [
        (alias, location_id)
        for alias, location_id in catalog.gas_aliases.items()
        if alias in compact
    ]
    if not matches:
        raise WorkbenchException(UNKNOWN_GAS_LOCATION, f"Unknown gas location in {raw}")
    matches.sort(key=lambda item: len(item[0]), reverse=True)
    return matches[0][1]


def gas_index_keywords(catalog: RegistryCatalog | None = None) -> dict[str, str]:
    catalog = catalog or load_registry_catalog()
    rules = ((catalog.market_rules.get("gas") or {}).get("index_family_keywords") or {})
    return {str(key).upper(): str(value).upper() for key, value in rules.items()}


def _mapping_candidates(mapping_id: str, mapping: dict[str, Any]) -> set[str]:
    values = {
        mapping_id,
        str(mapping.get("source_contract_id") or ""),
        str(mapping.get("contract_symbol") or ""),
    }
    values.update(str(alias) for alias in mapping.get("aliases") or [])
    return {compact_label(value) for value in values if compact_label(value)}


def lookup_forward_fundamental_mapping(raw: str, catalog: RegistryCatalog | None = None) -> dict[str, Any] | None:
    catalog = catalog or load_registry_catalog()
    raw_compact = compact_label(raw)
    raw_tokens = {compact_label(token) for token in re.split(r"\s+", raw.upper()) if compact_label(token)}
    for mapping_id, mapping in catalog.forward_fundamental_mappings.items():
        candidates = _mapping_candidates(mapping_id, mapping)
        if raw_compact in candidates or bool(raw_tokens & candidates):
            record = dict(mapping)
            record.setdefault("mapping_id", mapping_id)
            return record
    return None


def find_forward_fundamental_mapping(raw: str, catalog: RegistryCatalog | None = None) -> dict[str, Any]:
    mapping = lookup_forward_fundamental_mapping(raw, catalog)
    if mapping is None:
        raise WorkbenchException(UNKNOWN_PRODUCT, f"Unknown forward/fundamental mapping for {raw}")
    return mapping


def lookup_option_contract(raw: str, catalog: RegistryCatalog | None = None) -> dict[str, Any] | None:
    catalog = catalog or load_registry_catalog()
    raw_compact = compact_label(raw)
    raw_tokens = {compact_label(token) for token in re.split(r"\s+", raw.upper()) if compact_label(token)}
    for contract_id, contract in catalog.option_contracts.items():
        values = {
            contract_id,
            str(contract.get("contract_symbol") or ""),
            str(contract.get("product_name") or ""),
            str(contract.get("product_guide_id") or ""),
        }
        candidates = {compact_label(value) for value in values if compact_label(value)}
        if raw_compact in candidates or bool(raw_tokens & candidates):
            record = dict(contract)
            record.setdefault("option_contract_id", contract_id)
            return record
    return None


def find_option_contract(raw: str, catalog: RegistryCatalog | None = None) -> dict[str, Any]:
    contract = lookup_option_contract(raw, catalog)
    if contract is None:
        raise WorkbenchException(UNKNOWN_PRODUCT, f"Unknown option contract for {raw}")
    return contract
