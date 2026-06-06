from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator

from ..exceptions import WorkbenchException
from ..models import PjmLmpObservation, PjmPnode, PowerPriceState, PriceSurfacePoint
from ..registry import load_yaml_unique
from ..serialization import to_plain

POWER_PRICE_ERROR = "POWER_PRICE_ERROR"
UNKNOWN_POWER_PRICE_FEED = "UNKNOWN_POWER_PRICE_FEED"
UNKNOWN_PJM_PNODE = "UNKNOWN_PJM_PNODE"
UNSUPPORTED_POWER_PRICE_COMPONENT = "UNSUPPORTED_POWER_PRICE_COMPONENT"

LMP_COMPONENT_VALUES = {
    "FULL_LMP": "total_lmp",
    "CONGESTION": "congestion_price",
    "MARGINAL_LOSS": "marginal_loss_price",
    "SYSTEM_ENERGY": "system_energy_price",
}
PJM_EPT_ZONE = ZoneInfo("America/New_York")


def load_power_system_price_feeds(registry_dir: Path) -> dict[str, dict[str, Any]]:
    payload = load_yaml_unique(Path(registry_dir) / "power_system_price_feeds.yaml")
    if not isinstance(payload, dict):
        raise WorkbenchException(POWER_PRICE_ERROR, "power_system_price_feeds.yaml must be a mapping")
    return {str(key): dict(value) for key, value in payload.items()}


def validate_power_system_price_feed_contracts(registry_dir: Path) -> dict[str, Any]:
    feeds = load_power_system_price_feeds(registry_dir)
    approved_lmp_feeds: list[str] = []
    metadata_feeds: list[str] = []
    for feed_id, feed in feeds.items():
        if feed.get("status") != "approved_core":
            continue
        contract = dict(feed.get("source_product_contract") or {})
        product_type = str(feed.get("product_type"))
        if product_type == "pricing_node_master":
            _validate_pnode_source_contract(feed_id, feed, contract)
            metadata_feeds.append(feed_id)
        elif product_type == "locational_marginal_price":
            _validate_lmp_source_contract(feed_id, feed, contract)
            approved_lmp_feeds.append(feed_id)
    return {
        "approved_lmp_feeds": sorted(approved_lmp_feeds),
        "metadata_feeds": sorted(metadata_feeds),
    }


def _validate_pnode_source_contract(feed_id: str, feed: dict[str, Any], contract: dict[str, Any]) -> None:
    expected = {
        "observation_role": "metadata",
        "delivery_window_policy": "effective_dated_metadata",
        "pnode_identity_policy": "official_pnode_master",
        "component_policy": "not_applicable",
        "version_policy": "effective_dated",
        "canonical_promotion_policy": "metadata_verification_only",
    }
    _require_contract_values(feed_id, contract, expected)
    time_columns = dict(feed.get("time_columns") or {})
    if not time_columns.get("effective_start") or not time_columns.get("effective_end"):
        raise WorkbenchException(POWER_PRICE_ERROR, f"{feed_id} metadata contract requires effective start and end columns")


def _validate_lmp_source_contract(feed_id: str, feed: dict[str, Any], contract: dict[str, Any]) -> None:
    expected = {
        "observation_role": "source_price_observation",
        "delivery_window_policy": "utc_hourly_delivery_windows_required",
        "pnode_identity_policy": "approved_location_pnode_required",
        "component_policy": "full_lmp_and_source_components_required",
        "version_policy": "current_row_filter_required",
        "canonical_promotion_policy": "approved_pnode_and_components_required",
    }
    _require_contract_values(feed_id, contract, expected)
    time_columns = dict(feed.get("time_columns") or {})
    if not time_columns.get("delivery_start_utc"):
        raise WorkbenchException(POWER_PRICE_ERROR, f"{feed_id} LMP contract requires a UTC delivery-start column")
    version_columns = dict(feed.get("version_columns") or {})
    if not version_columns.get("row_is_current") or not version_columns.get("version_nbr"):
        raise WorkbenchException(POWER_PRICE_ERROR, f"{feed_id} LMP contract requires row_is_current and version_nbr columns")
    required_filters = dict(feed.get("required_filters") or {})
    if str(required_filters.get("row_is_current")) != "1":
        raise WorkbenchException(POWER_PRICE_ERROR, f"{feed_id} LMP contract requires row_is_current required filter equal to 1")
    expected_components = ["FULL_LMP", "CONGESTION", "MARGINAL_LOSS", "SYSTEM_ENERGY"]
    supported = list(feed.get("supported_price_components") or [])
    source_components = list(feed.get("source_components") or [])
    if supported != expected_components or source_components != expected_components:
        raise WorkbenchException(
            POWER_PRICE_ERROR,
            f"{feed_id} LMP contract requires full source component coverage: {', '.join(expected_components)}",
        )
    value_columns = dict(feed.get("value_columns") or {})
    missing = [key for key in ["full_lmp", "congestion", "marginal_loss", "system_energy"] if not value_columns.get(key)]
    if missing:
        raise WorkbenchException(POWER_PRICE_ERROR, f"{feed_id} LMP contract missing value columns: {', '.join(missing)}")


def _require_contract_values(feed_id: str, contract: dict[str, Any], expected: dict[str, str]) -> None:
    for key, value in expected.items():
        if contract.get(key) != value:
            raise WorkbenchException(
                POWER_PRICE_ERROR,
                f"{feed_id} source product contract requires {key}={value}, found {contract.get(key)!r}",
            )


def _parse_utc(value: Any, label: str) -> datetime:
    raw = str(value).strip()
    if not raw:
        raise WorkbenchException(POWER_PRICE_ERROR, f"{label} is required")
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        for fmt in ["%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y"]:
            try:
                parsed = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            raise WorkbenchException(POWER_PRICE_ERROR, f"{label} is not a recognized timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _parse_pjm_ept_candidates(value: Any, label: str) -> list[datetime]:
    raw = str(value).strip()
    if not raw:
        raise WorkbenchException(POWER_PRICE_ERROR, f"{label} is required")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        for fmt in ["%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y"]:
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        else:
            raise WorkbenchException(POWER_PRICE_ERROR, f"{label} is not a recognized EPT timestamp: {value}") from exc
    if parsed.tzinfo is not None:
        return [parsed.astimezone(timezone.utc).replace(microsecond=0)]
    candidates = {
        parsed.replace(tzinfo=PJM_EPT_ZONE, fold=fold).astimezone(timezone.utc).replace(microsecond=0)
        for fold in [0, 1]
    }
    return sorted(candidates)


def _validate_utc_hourly_delivery_start(feed_id: str, start: datetime, ept_value: Any | None) -> None:
    if start.minute != 0 or start.second != 0 or start.microsecond != 0:
        raise WorkbenchException(POWER_PRICE_ERROR, f"{feed_id} delivery_start must align to an exact UTC hour: {_iso_z(start)}")
    if ept_value in {None, ""}:
        return
    ept_candidates = _parse_pjm_ept_candidates(ept_value, "delivery_start_ept")
    if start not in ept_candidates:
        raise WorkbenchException(
            POWER_PRICE_ERROR,
            f"{feed_id} delivery_start_utc {_iso_z(start)} does not match PJM EPT timestamp {ept_value!r}",
        )


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(row: dict[str, Any], column: str | None, label: str) -> Any:
    if not column or column not in row or row[column] in {None, ""}:
        raise WorkbenchException(POWER_PRICE_ERROR, f"Missing required {label}; expected column {column!r}")
    return row[column]


def _optional(row: dict[str, Any], column: str | None) -> Any:
    if not column:
        return None
    value = row.get(column)
    return None if value == "" else value


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in {"true", "1", "yes", "y"}:
        return True
    if raw in {"false", "0", "no", "n"}:
        return False
    raise WorkbenchException(POWER_PRICE_ERROR, f"Invalid boolean value: {value!r}")


def _int_or_none(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(float(value))


def _float_or_none(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def _power_locations_by_pnode(registry_dir: Path) -> dict[int, tuple[str, dict[str, Any]]]:
    payload = load_yaml_unique(Path(registry_dir) / "power_locations.yaml")
    if not isinstance(payload, dict):
        raise WorkbenchException(POWER_PRICE_ERROR, "power_locations.yaml must be a mapping")
    mapped: dict[int, tuple[str, dict[str, Any]]] = {}
    for location_id, record in payload.items():
        if not isinstance(record, dict) or record.get("commodity") != "power":
            continue
        pnode_id = record.get("pjm_pnode_id")
        if pnode_id is None:
            continue
        key = int(pnode_id)
        if key in mapped:
            raise WorkbenchException(POWER_PRICE_ERROR, f"PJM pnode maps to multiple power locations: {key}")
        mapped[key] = (str(location_id), dict(record))
    return mapped


def normalize_pjm_pnode_records(rows: list[dict[str, Any]], registry_dir: Path) -> list[PjmPnode]:
    feeds = load_power_system_price_feeds(registry_dir)
    feed = feeds.get("PJM_PNODE")
    if feed is None:
        raise WorkbenchException(UNKNOWN_POWER_PRICE_FEED, "Missing PJM_PNODE price feed descriptor")
    pnode_columns = dict(feed["pnode_columns"])
    time_columns = dict(feed["time_columns"])
    pnodes: list[PjmPnode] = []
    for row_number, row in enumerate(rows, start=1):
        effective_start = _iso_z(_parse_utc(_required(row, time_columns.get("effective_start"), "effective_start"), "effective_start"))
        effective_end = _iso_z(_parse_utc(_required(row, time_columns.get("effective_end"), "effective_end"), "effective_end"))
        pnodes.append(
            PjmPnode(
                source=str(feed["source"]),
                pnode_id=int(_required(row, pnode_columns.get("pnode_id"), "pnode_id")),
                pnode_name=str(_required(row, pnode_columns.get("pnode_name"), "pnode_name")),
                pnode_type=None if _optional(row, pnode_columns.get("pnode_type")) is None else str(_optional(row, pnode_columns.get("pnode_type"))),
                pnode_subtype=None if _optional(row, pnode_columns.get("pnode_subtype")) is None else str(_optional(row, pnode_columns.get("pnode_subtype"))),
                zone=None if _optional(row, pnode_columns.get("zone")) is None else str(_optional(row, pnode_columns.get("zone"))),
                voltage_level=None if _optional(row, pnode_columns.get("voltage")) is None else str(_optional(row, pnode_columns.get("voltage"))),
                effective_start=effective_start,
                effective_end=effective_end,
                lineage={
                    "source_feed_id": "PJM_PNODE",
                    "data_miner_feed": feed["data_miner_feed"],
                    "raw_row_id": str(row_number),
                },
            )
        )
    return pnodes


def verify_pjm_location_pnodes(pnodes: list[PjmPnode], registry_dir: Path, as_of: str | None = None) -> dict[str, dict[str, Any]]:
    official_by_id = {item.pnode_id: item for item in pnodes}
    effective_as_of = _parse_utc(as_of, "as_of") if as_of else None
    verified: dict[str, dict[str, Any]] = {}
    for pnode_id, (location_id, location) in _power_locations_by_pnode(registry_dir).items():
        official = official_by_id.get(pnode_id)
        if official is None:
            continue
        expected_name = str(location.get("pjm_pnode_name") or "").upper()
        if expected_name and official.pnode_name.upper() != expected_name:
            raise WorkbenchException(POWER_PRICE_ERROR, f"PJM pnode name mismatch for {location_id}: {official.pnode_name}")
        expected_type = str(location.get("pjm_pnode_type") or "").upper()
        observed_types = {str(value).upper() for value in [official.pnode_type, official.pnode_subtype] if value}
        if expected_type and expected_type not in observed_types:
            raise WorkbenchException(POWER_PRICE_ERROR, f"PJM pnode type mismatch for {location_id}: {observed_types}")
        if effective_as_of is not None:
            effective_start = _parse_utc(official.effective_start, "pnode.effective_start")
            effective_end = _parse_utc(official.effective_end, "pnode.effective_end")
            if not (effective_start <= effective_as_of < effective_end):
                raise WorkbenchException(
                    POWER_PRICE_ERROR,
                    f"PJM pnode {pnode_id} for {location_id} is not effective at {as_of}",
                )
        verified[location_id] = {
            "pnode_id": pnode_id,
            "pnode_name": official.pnode_name,
            "pnode_type": official.pnode_type,
            "pnode_subtype": official.pnode_subtype,
            "effective_start": official.effective_start,
            "effective_end": official.effective_end,
            "effective_as_of": _iso_z(effective_as_of) if effective_as_of is not None else None,
            "verification_status": "official_pjm_data_miner_verified",
        }
    return verified


def normalize_pjm_lmp_records(
    feed_id: str,
    rows: list[dict[str, Any]],
    registry_dir: Path,
    as_of: str | None = None,
    require_current: bool = True,
) -> list[PjmLmpObservation]:
    feeds = load_power_system_price_feeds(registry_dir)
    feed = feeds.get(feed_id)
    if feed is None or feed.get("product_type") != "locational_marginal_price":
        raise WorkbenchException(UNKNOWN_POWER_PRICE_FEED, f"Unknown PJM LMP price feed: {feed_id}")
    if feed.get("status") != "approved_core":
        raise WorkbenchException(POWER_PRICE_ERROR, f"PJM LMP price feed is not approved for normalization: {feed_id}")
    if "FULL_LMP" not in set(feed.get("supported_price_components") or []):
        raise WorkbenchException(UNSUPPORTED_POWER_PRICE_COMPONENT, f"{feed_id} does not support FULL_LMP")
    time_columns = dict(feed["time_columns"])
    pnode_columns = dict(feed["pnode_columns"])
    value_columns = dict(feed["value_columns"])
    version_columns = dict(feed.get("version_columns") or {})
    observations: list[PjmLmpObservation] = []

    for row_number, row in enumerate(rows, start=1):
        current_column = version_columns.get("row_is_current")
        row_is_current = _bool(row.get(current_column, True)) if current_column else True
        if require_current and not row_is_current:
            raise WorkbenchException(POWER_PRICE_ERROR, f"{feed_id} row {row_number} is not current")
        start = _parse_utc(_required(row, time_columns.get("delivery_start_utc"), "delivery_start"), "delivery_start")
        delivery_start_ept = _optional(row, time_columns.get("delivery_start_ept"))
        _validate_utc_hourly_delivery_start(feed_id, start, delivery_start_ept)
        total_lmp = float(_required(row, value_columns.get("full_lmp"), "full_lmp"))
        observations.append(
            PjmLmpObservation(
                as_of=as_of or _iso_z(start),
                source=str(feed["source"]),
                market=str(feed["market"]),
                market_run=str(feed["market_run"]),
                pnode_id=int(_required(row, pnode_columns.get("pnode_id"), "pnode_id")),
                pnode_name=str(_required(row, pnode_columns.get("pnode_name"), "pnode_name")),
                pnode_type=None if _optional(row, pnode_columns.get("pnode_type")) is None else str(_optional(row, pnode_columns.get("pnode_type"))),
                zone=None if _optional(row, pnode_columns.get("zone")) is None else str(_optional(row, pnode_columns.get("zone"))),
                delivery_start=_iso_z(start),
                delivery_end=_iso_z(start + timedelta(hours=1)),
                total_lmp=total_lmp,
                congestion_price=_float_or_none(_optional(row, value_columns.get("congestion"))),
                marginal_loss_price=_float_or_none(_optional(row, value_columns.get("marginal_loss"))),
                system_energy_price=_float_or_none(_optional(row, value_columns.get("system_energy"))),
                quote_unit=str(feed["value_unit"]),
                row_is_current=row_is_current,
                version_nbr=_int_or_none(_optional(row, version_columns.get("version_nbr"))),
                lineage={
                    "source_feed_id": feed_id,
                    "data_miner_feed": feed["data_miner_feed"],
                    "raw_row_id": str(row_number),
                    "source_components": list(feed.get("source_components") or []),
                    "delivery_start_ept": delivery_start_ept,
                },
            )
        )
    return observations


def _hour_period_id(delivery_start: str) -> str:
    parsed = _parse_utc(delivery_start, "delivery_start")
    return "HOUR_" + parsed.strftime("%Y%m%dT%H%M%SZ")


def _observation_component_value(observation: PjmLmpObservation, component: str) -> float:
    attr = LMP_COMPONENT_VALUES.get(component)
    if attr is None:
        raise WorkbenchException(UNSUPPORTED_POWER_PRICE_COMPONENT, f"Unsupported PJM LMP price component: {component}")
    value = getattr(observation, attr)
    if value is None:
        raise WorkbenchException(POWER_PRICE_ERROR, f"Missing PJM LMP component value for {component} at {observation.pnode_id} {observation.delivery_start}")
    return float(value)


def pjm_lmp_observations_to_price_surface_points(
    observations: list[PjmLmpObservation],
    registry_dir: Path,
) -> list[PriceSurfacePoint]:
    locations = _power_locations_by_pnode(registry_dir)
    feeds = load_power_system_price_feeds(registry_dir)
    points: list[PriceSurfacePoint] = []
    for observation in observations:
        mapping = locations.get(observation.pnode_id)
        if mapping is None:
            raise WorkbenchException(UNKNOWN_PJM_PNODE, f"Unsupported PJM pnode for canonical price surface: {observation.pnode_id}")
        location_id, location = mapping
        expected_name = str(location.get("pjm_pnode_name") or "").upper()
        if expected_name and observation.pnode_name.upper() != expected_name:
            raise WorkbenchException(POWER_PRICE_ERROR, f"PJM LMP pnode name mismatch for {location_id}: {observation.pnode_name}")
        period_id = _hour_period_id(observation.delivery_start)
        feed_id = str(observation.lineage.get("source_feed_id"))
        feed = feeds.get(feed_id)
        if feed is None:
            raise WorkbenchException(UNKNOWN_POWER_PRICE_FEED, f"Unknown PJM LMP observation feed: {feed_id}")
        components = list(feed.get("supported_price_components") or [])
        if "FULL_LMP" not in components:
            raise WorkbenchException(UNSUPPORTED_POWER_PRICE_COMPONENT, f"{feed_id} does not support FULL_LMP")
        source_component_values = {
            "FULL_LMP": observation.total_lmp,
            "CONGESTION": observation.congestion_price,
            "MARGINAL_LOSS": observation.marginal_loss_price,
            "SYSTEM_ENERGY": observation.system_energy_price,
        }
        for component in components:
            price = _observation_component_value(observation, str(component))
            index_base = f"PJM.{location_id}.{observation.market_run}.{component}.HOURLY"
            points.append(
                PriceSurfacePoint(
                    as_of=observation.as_of,
                    index_id=f"{index_base}.{period_id}",
                    location_id=location_id,
                    commodity="power",
                    period_id=period_id,
                    price=price,
                    quote_unit=observation.quote_unit,
                    source=observation.source,
                    source_role="authoritative_iso_publication",
                    lineage={
                        **observation.lineage,
                        "index_base": index_base,
                        "price_component": component,
                        "market_run": observation.market_run,
                        "pnode_id": observation.pnode_id,
                        "pnode_name": observation.pnode_name,
                        "pnode_source_status": location.get("pnode_source_status"),
                        "delivery_start": observation.delivery_start,
                        "delivery_end": observation.delivery_end,
                        "row_is_current": observation.row_is_current,
                        "version_nbr": observation.version_nbr,
                        "source_component_values": source_component_values,
                    },
                )
            )
    return points


def build_pjm_power_price_state(
    pnodes: list[PjmPnode],
    observations: list[PjmLmpObservation],
    as_of: str,
    registry_dir: Path,
    run_id: str = "pjm-power-prices",
) -> PowerPriceState:
    points = pjm_lmp_observations_to_price_surface_points(observations, registry_dir)
    source_products: dict[str, list[dict[str, Any]]] = {}
    if pnodes:
        source_products["PJM_PNODE"] = [to_plain(item) for item in pnodes]
    for observation in observations:
        feed_id = str(observation.lineage.get("source_feed_id"))
        source_products.setdefault(feed_id, []).append(to_plain(observation))
    return PowerPriceState(
        run_id=run_id,
        as_of=as_of,
        source_products=source_products,
        price_surface_points=[to_plain(item) for item in points],
        derived=[],
        gaps=[],
        lineage={
            "pnode_count": len(pnodes),
            "lmp_observation_count": len(observations),
            "price_surface_point_count": len(points),
            "pnode_verifications": verify_pjm_location_pnodes(pnodes, registry_dir, as_of=as_of) if pnodes else {},
        },
    )


def build_pjm_power_price_artifacts(
    pnodes: list[PjmPnode],
    observations: list[PjmLmpObservation],
    as_of: str,
    registry_dir: Path,
    run_id: str = "pjm-power-prices",
) -> dict[str, Any]:
    state = build_pjm_power_price_state(pnodes, observations, as_of, registry_dir, run_id=run_id)
    state_payload = to_plain(state)
    points = state_payload["price_surface_points"]
    return {
        "pjm_power_prices": state_payload,
        "price_surface_points": points,
        "inputs": {
            "prices": points,
        },
        "source_lineage": [
            {
                "source": "PJM Data Miner",
                "artifact": "pjm_power_prices",
                "run_id": run_id,
            }
        ],
    }


def validate_power_price_state(state: PowerPriceState | dict[str, Any], schema_dir: Path) -> None:
    schema = load_yaml_unique(Path(schema_dir) / "power_price_state.schema.json")
    payload = to_plain(state)
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(POWER_PRICE_ERROR, f"power price state{suffix}: {first.message}")
