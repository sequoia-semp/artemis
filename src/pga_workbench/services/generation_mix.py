from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..exceptions import WorkbenchException
from ..models import GenerationMixObservation, GenerationMixState
from ..registry import load_yaml_unique
from ..serialization import to_plain

GENERATION_MIX_ERROR = "GENERATION_MIX_ERROR"
UNKNOWN_GENERATION_FUEL = "UNKNOWN_GENERATION_FUEL"


def load_power_generation_mix_feeds(registry_dir: Path) -> dict[str, dict[str, Any]]:
    payload = load_yaml_unique(Path(registry_dir) / "power_generation_mix_feeds.yaml")
    if not isinstance(payload, dict):
        raise WorkbenchException(GENERATION_MIX_ERROR, "power_generation_mix_feeds.yaml must be a mapping")
    return {str(key): dict(value) for key, value in payload.items()}


def load_power_generation_fuels(registry_dir: Path) -> dict[str, dict[str, Any]]:
    payload = load_yaml_unique(Path(registry_dir) / "power_generation_fuels.yaml")
    if not isinstance(payload, dict):
        raise WorkbenchException(GENERATION_MIX_ERROR, "power_generation_fuels.yaml must be a mapping")
    return {str(key): dict(value) for key, value in payload.items()}


def _compact(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def _fuel_aliases(registry_dir: Path, market: str) -> dict[str, tuple[str, dict[str, Any]]]:
    aliases: dict[str, tuple[str, dict[str, Any]]] = {}
    for fuel_id, record in load_power_generation_fuels(registry_dir).items():
        source_aliases = dict(record.get("source_aliases") or {})
        for alias in source_aliases.get(market, []):
            key = _compact(str(alias))
            existing = aliases.get(key)
            if existing is not None and existing[0] != fuel_id:
                raise WorkbenchException(GENERATION_MIX_ERROR, f"Generation fuel alias maps to multiple fuels: {alias}")
            aliases[key] = (fuel_id, dict(record))
    return aliases


def normalize_generation_fuel(value: str, registry_dir: Path, market: str = "PJM") -> tuple[str, dict[str, Any]]:
    aliases = _fuel_aliases(registry_dir, market)
    key = _compact(value)
    if key not in aliases:
        raise WorkbenchException(UNKNOWN_GENERATION_FUEL, f"Unknown {market} generation fuel type: {value}")
    return aliases[key]


def _parse_utc(value: Any, label: str) -> datetime:
    raw = str(value).strip()
    if not raw:
        raise WorkbenchException(GENERATION_MIX_ERROR, f"{label} is required")
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
            raise WorkbenchException(GENERATION_MIX_ERROR, f"{label} is not a recognized timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required(row: dict[str, Any], column: str, label: str) -> Any:
    if column not in row or row[column] in {None, ""}:
        raise WorkbenchException(GENERATION_MIX_ERROR, f"Missing required {label}; expected column {column!r}")
    return row[column]


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in {"true", "1", "yes", "y"}:
        return True
    if raw in {"false", "0", "no", "n"}:
        return False
    raise WorkbenchException(GENERATION_MIX_ERROR, f"Invalid boolean value: {value!r}")


def _float_or_none(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def normalize_pjm_generation_mix_records(
    feed_id: str,
    rows: list[dict[str, Any]],
    registry_dir: Path,
    as_of: str | None = None,
) -> list[GenerationMixObservation]:
    feeds = load_power_generation_mix_feeds(registry_dir)
    feed = feeds.get(feed_id)
    if feed is None:
        raise WorkbenchException(GENERATION_MIX_ERROR, f"Unknown generation mix feed: {feed_id}")
    time_columns = dict(feed["time_columns"])
    fuel_columns = dict(feed["fuel_columns"])
    value_columns = dict(feed["value_columns"])
    observations: list[GenerationMixObservation] = []

    for row_number, row in enumerate(rows, start=1):
        start = _parse_utc(_required(row, time_columns["delivery_start_utc"], "delivery_start"), "delivery_start")
        raw_fuel_type = str(_required(row, fuel_columns["fuel_type"], "fuel_type"))
        fuel_id, fuel = normalize_generation_fuel(raw_fuel_type, registry_dir, market=str(feed["market"]))
        observed_renewable = _bool(_required(row, fuel_columns["is_renewable"], "is_renewable"))
        if observed_renewable != bool(fuel["is_renewable"]):
            raise WorkbenchException(GENERATION_MIX_ERROR, f"Renewable flag mismatch for {raw_fuel_type}")
        observations.append(
            GenerationMixObservation(
                as_of=as_of or _iso_z(start),
                source=str(feed["source"]),
                market=str(feed["market"]),
                location_id="PJM_RTO",
                fuel_id=fuel_id,
                raw_fuel_type=raw_fuel_type,
                delivery_start=_iso_z(start),
                delivery_end=_iso_z(start + timedelta(hours=1)),
                mw=float(_required(row, value_columns["mw"], "mw")),
                fuel_percentage_of_total=_float_or_none(row.get(value_columns.get("fuel_percentage_of_total"))),
                is_renewable=observed_renewable,
                unit=str(feed["value_unit"]),
                lineage={
                    "source_feed_id": feed_id,
                    "data_miner_feed": feed["data_miner_feed"],
                    "raw_row_id": str(row_number),
                    "delivery_start_ept": row.get(time_columns["delivery_start_ept"]),
                    "fuel_family": fuel["fuel_family"],
                    "source_product": "generation_mix",
                },
            )
        )
    return observations


def build_generation_mix_state(
    observations: list[GenerationMixObservation],
    as_of: str,
    run_id: str = "pjm-generation-mix",
) -> GenerationMixState:
    source_products: dict[str, list[dict[str, Any]]] = {}
    for observation in observations:
        source_products.setdefault(str(observation.lineage["source_feed_id"]), []).append(to_plain(observation))
    return GenerationMixState(
        run_id=run_id,
        as_of=as_of,
        source_products=source_products,
        observations=[to_plain(item) for item in observations],
        gaps=[],
        lineage={
            "observation_count": len(observations),
            "fuel_ids": sorted({item.fuel_id for item in observations}),
            "renewable_mw": sum(item.mw for item in observations if item.is_renewable),
            "total_mw": sum(item.mw for item in observations),
        },
    )


def _generation_mix_view_payload(payload: dict[str, Any], run_id: str) -> dict[str, Any]:
    observations = list(payload["observations"])
    lineage = dict(payload.get("lineage") or {})
    total_mw = float(lineage.get("total_mw") or 0.0)
    renewable_mw = float(lineage.get("renewable_mw") or 0.0)
    renewable_share = renewable_mw / total_mw if total_mw else None
    by_fuel = sorted(
        [
            {
                "fuel_id": str(item["fuel_id"]),
                "mw": float(item["mw"]),
                "is_renewable": bool(item["is_renewable"]),
                "source": str(item["source"]),
            }
            for item in observations
        ],
        key=lambda item: (-item["mw"], item["fuel_id"]),
    )
    top_fuel = by_fuel[0] if by_fuel else None
    summary = (
        "PJM generation mix built from source-backed artifacts: "
        f"{len(observations)} fuel observations, {total_mw:g} MW total generation, "
        f"{renewable_mw:g} MW renewable generation."
    )
    drivers: list[dict[str, Any]] = [
        {
            "name": "total_generation_mw",
            "direction": "source_observed",
            "value": total_mw,
            "unit": "MW",
            "source_artifact": "pjm_generation_mix",
        },
        {
            "name": "renewable_generation_mw",
            "direction": "source_observed",
            "value": renewable_mw,
            "unit": "MW",
            "source_artifact": "pjm_generation_mix",
        },
    ]
    if top_fuel is not None:
        drivers.append(
            {
                "name": "largest_generation_fuel",
                "direction": "source_observed",
                "fuel_id": top_fuel["fuel_id"],
                "value": top_fuel["mw"],
                "unit": "MW",
                "source_artifact": "pjm_generation_mix",
            }
        )

    return {
        "summary": summary,
        "stance_summary": "Generation mix is source-observed context only; no trading stance is inferred.",
        "market_scope": {
            "commodity": "power",
            "regions": ["PJM"],
            "exchange_scope": [],
        },
        "drivers": drivers,
        "current_day_view": {
            "generation_mix": {
                "market": "PJM",
                "location_id": "PJM_RTO",
                "total_mw": total_mw,
                "renewable_mw": renewable_mw,
                "renewable_share": renewable_share,
                "fuel_count": len(observations),
                "top_fuels": by_fuel[:5],
            }
        },
        "evidence": [
            {
                "source": "PJM Data Miner",
                "artifact": "pjm_generation_mix",
                "run_id": run_id,
                "observation_count": len(observations),
                "fuel_ids": list(lineage.get("fuel_ids") or []),
            }
        ],
    }


def build_pjm_generation_mix_artifacts(
    observations: list[GenerationMixObservation],
    as_of: str,
    run_id: str = "pjm-generation-mix",
) -> dict[str, Any]:
    state = build_generation_mix_state(observations, as_of, run_id=run_id)
    payload = to_plain(state)
    return {
        "pjm_generation_mix": payload,
        "generation_mix_observations": payload["observations"],
        "inputs": {
            "generation_mix": payload["observations"],
        },
        "source_lineage": [
            {
                "source": "PJM Data Miner",
                "artifact": "pjm_generation_mix",
                "run_id": run_id,
            }
        ],
        **_generation_mix_view_payload(payload, run_id),
    }


def validate_generation_mix_state(state: GenerationMixState | dict[str, Any], schema_dir: Path) -> None:
    schema = load_yaml_unique(Path(schema_dir) / "generation_mix_state.schema.json")
    payload = to_plain(state)
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(GENERATION_MIX_ERROR, f"generation mix state{suffix}: {first.message}")
