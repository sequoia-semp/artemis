from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException, UNKNOWN_PRODUCT
from ..indices import MarketIndex, normalize_exchange_contract_index, normalize_gas_index, normalize_power_index
from ..models import NormalizedPosition, PriceSurfacePoint, RawMark, RawPosition
from ..periods import parse_period
from ..quantities import gas_contracts_to_total_mmbtu, power_mw_to_mwh
from ..spreads import decompose_power_spread


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    return float(value)


def _int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    return int(float(value))


def _tags(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace(";", ",").split(",") if item.strip()]


def _metadata(value: Any) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return dict(value)
    parsed = json.loads(str(value))
    if not isinstance(parsed, dict):
        raise WorkbenchException("POSITION_METADATA_INVALID", "Position metadata must be a JSON object")
    return parsed


def market_index_from_raw(raw_product: str) -> MarketIndex:
    compact = raw_product.strip().upper()
    if "/" in compact:
        raise WorkbenchException(UNKNOWN_PRODUCT, "Spreads are positions, not price surface indexes")
    try:
        return normalize_exchange_contract_index(raw_product)
    except WorkbenchException as exc:
        if exc.code != UNKNOWN_PRODUCT:
            raise
    power_tokens = set(compact.replace("-", " ").split())
    if power_tokens & {"WH", "AD", "NI"}:
        return normalize_power_index(raw_product)
    return normalize_gas_index(raw_product)


def raw_mark_from_row(row: dict[str, Any], row_number: int) -> RawMark:
    return RawMark(
        as_of=row["as_of"],
        raw_product=row["raw_product"],
        raw_period=row["raw_period"],
        price=float(row["price"]),
        source=row.get("source") or "local_marks_csv",
        source_role=row.get("source_role") or "authoritative_input",
        raw_row_id=row.get("raw_row_id") or str(row_number),
    )


def normalize_mark(mark: RawMark) -> PriceSurfacePoint:
    idx = market_index_from_raw(mark.raw_product)
    period = parse_period(mark.raw_period, idx.commodity)
    return PriceSurfacePoint(
        as_of=mark.as_of,
        index_id=f"{idx.index_id}.{period.normalized_label}",
        location_id=idx.location_id,
        commodity=idx.commodity,
        period_id=period.normalized_label,
        price=mark.price,
        quote_unit=idx.quote_unit,
        source=mark.source,
        source_role=mark.source_role,
        lineage={
            "raw_product": mark.raw_product,
            "raw_period": mark.raw_period,
            "raw_row_id": mark.raw_row_id,
            "defaulted": idx.is_defaulted,
            "default_reason": idx.default_reason,
            "source_contract_id": idx.source_contract_id,
            "mapping_id": idx.mapping_id,
        },
    )


def normalize_marks(rows: list[dict[str, Any]]) -> list[PriceSurfacePoint]:
    return [normalize_mark(raw_mark_from_row(row, i + 1)) for i, row in enumerate(rows)]


def raw_position_from_row(row: dict[str, Any], row_number: int) -> RawPosition:
    return RawPosition(
        as_of=row["as_of"],
        raw_product=row["raw_product"],
        raw_period=row["raw_period"],
        raw_quantity=float(row["raw_quantity"]),
        quantity_unit=row.get("quantity_unit") or "MW",
        position_id=row.get("position_id") or f"row-{row_number}",
        raw_mark=_float(row.get("raw_mark")),
        book=row.get("book") or None,
        strategy=row.get("strategy") or None,
        portfolio=row.get("portfolio") or None,
        sleeve=row.get("sleeve") or None,
        structure_id=row.get("structure_id") or None,
        tags=_tags(row.get("tags")),
        metadata=_metadata(row.get("metadata")),
        source=row.get("source") or "local_positions_csv",
        source_role=row.get("source_role") or "authoritative_input",
        reference_hours=_float(row.get("reference_hours")),
        delivery_days=_int(row.get("delivery_days")),
    )


def _mark_lookup(price_surface: list[PriceSurfacePoint]) -> dict[tuple[str, str], float]:
    return {(point.index_id.rsplit(".", 1)[0], point.period_id): point.price for point in price_surface}


def normalize_position(position: RawPosition, price_surface: list[PriceSurfacePoint] | None = None) -> NormalizedPosition:
    period = parse_period(position.raw_period, "power" if "/" in position.raw_product else "generic")
    price_lookup = _mark_lookup(price_surface or [])
    product = position.raw_product.strip().upper()

    decomposition: dict[str, Any] = {}
    exposure_bases: list[dict[str, Any]] = []
    if "/" in product:
        spread = decompose_power_spread(product, position.raw_quantity)
        commodity = "power"
        index_base = f"SPREAD.PJM.{spread.quote_label}.FULL_LMP.ATC"
        location_id = spread.quote_label
        quote_unit = "USD_per_MWh"
        normalized_product = {
            "product_type": "power_spread",
            "quote_label": spread.quote_label,
            "commodity": commodity,
            "index_id": f"{index_base}.{period.normalized_label}",
            "period_id": period.normalized_label,
            "quantity_unit": position.quantity_unit,
        }
        decomposition = {
            "first": spread.first,
            "second": spread.second,
            "first_leg_exposure": spread.first_leg_exposure,
            "second_leg_exposure": spread.second_leg_exposure,
        }
        exposure_bases = [
            {
                "index_base": f"PJM.{spread.first}.RT.FULL_LMP.ATC",
                "signed_quantity": spread.first_leg_exposure,
                "component": "first",
                "component_weight": 1.0,
                "exposure_type": "spread_leg",
            },
            {
                "index_base": f"PJM.{spread.second}.RT.FULL_LMP.ATC",
                "signed_quantity": spread.second_leg_exposure,
                "component": "second",
                "component_weight": -1.0,
                "exposure_type": "spread_leg",
            },
        ]
    else:
        idx = market_index_from_raw(position.raw_product)
        period = parse_period(position.raw_period, idx.commodity)
        commodity = idx.commodity
        index_base = idx.index_id
        location_id = idx.location_id
        quote_unit = idx.quote_unit
        normalized_product = {
            "product_type": "outright",
            "commodity": commodity,
            "location_id": location_id,
            "index_id": f"{index_base}.{period.normalized_label}",
            "period_id": period.normalized_label,
            "quantity_unit": position.quantity_unit,
            "is_defaulted": idx.is_defaulted,
            "default_reason": idx.default_reason,
        }
        exposure_bases = [
            {
                "index_base": index_base,
                "signed_quantity": position.raw_quantity,
                "component": None,
                "component_weight": 1.0,
                "exposure_type": "flat_price",
            }
        ]

    mark = position.raw_mark
    if mark is None:
        mark = price_lookup.get((index_base, period.normalized_label))

    derived_mwh = None
    derived_mmbtu = None
    valuation_quantity = position.raw_quantity
    if commodity == "power":
        hours = position.reference_hours
        if hours is None:
            raise WorkbenchException(UNKNOWN_PRODUCT, f"Power position requires reference_hours: {position.position_id}")
        derived_mwh = power_mw_to_mwh(position.raw_quantity, hours)
        valuation_quantity = derived_mwh
    elif position.quantity_unit.lower() == "contracts":
        if position.delivery_days is None:
            raise WorkbenchException(UNKNOWN_PRODUCT, f"Gas contract position requires delivery_days: {position.position_id}")
        derived_mmbtu = gas_contracts_to_total_mmbtu(position.raw_quantity, position.delivery_days)
        valuation_quantity = derived_mmbtu
    else:
        derived_mmbtu = position.raw_quantity
        valuation_quantity = derived_mmbtu

    market_value = valuation_quantity * mark if mark is not None else None
    identity = {
        "book": position.book,
        "strategy": position.strategy,
        "portfolio": position.portfolio,
        "sleeve": position.sleeve,
        "structure_id": position.structure_id,
        "tags": position.tags,
        "metadata": position.metadata,
    }
    position_lot = {
        "as_of": position.as_of,
        "position_id": position.position_id,
        "instrument_id": f"{index_base}.{period.normalized_label}",
        "instrument_type": normalized_product["product_type"],
        "raw_product": position.raw_product,
        "period_id": period.normalized_label,
        "signed_quantity": position.raw_quantity,
        "quantity_unit": position.quantity_unit,
        "mark": mark,
        "source": position.source,
        "source_role": position.source_role,
        **identity,
    }
    exposures = []
    for base in exposure_bases:
        exposure_quantity = float(base["signed_quantity"])
        exposure_mwh = None
        exposure_mmbtu = None
        if commodity == "power":
            exposure_mwh = power_mw_to_mwh(exposure_quantity, float(position.reference_hours or 0.0))
        elif position.quantity_unit.lower() == "contracts":
            exposure_mmbtu = gas_contracts_to_total_mmbtu(exposure_quantity, int(position.delivery_days or 0))
        else:
            exposure_mmbtu = exposure_quantity
        exposures.append(
            {
                "as_of": position.as_of,
                "position_id": position.position_id,
                "index_id": f"{base['index_base']}.{period.normalized_label}",
                "period_id": period.normalized_label,
                "signed_quantity": exposure_quantity,
                "quantity_unit": position.quantity_unit,
                "exposure_type": base["exposure_type"],
                "component": base["component"],
                "component_weight": base["component_weight"],
                "derived_MWh": exposure_mwh,
                "derived_MMBtu": exposure_mmbtu,
                "market_value": None if mark is None else (exposure_mwh if exposure_mwh is not None else exposure_mmbtu) * mark,
                **identity,
            }
        )
    return NormalizedPosition(
        as_of=position.as_of,
        position_id=position.position_id,
        raw={
            "raw_product": position.raw_product,
            "raw_period": position.raw_period,
            "raw_quantity": position.raw_quantity,
            "raw_mark": position.raw_mark,
            "source": position.source,
            "source_role": position.source_role,
        },
        identity=identity,
        normalized={**normalized_product, "quote_unit": quote_unit, "mark": mark},
        derived={
            "derived_MWh": derived_mwh,
            "derived_MMBtu": derived_mmbtu,
            "valuation_quantity": valuation_quantity,
            "market_value": market_value,
        },
        decomposition=decomposition,
        position_lot=position_lot,
        exposures=exposures,
    )


def normalize_positions(rows: list[dict[str, Any]], price_surface: list[PriceSurfacePoint] | None = None) -> list[NormalizedPosition]:
    return [normalize_position(raw_position_from_row(row, i + 1), price_surface) for i, row in enumerate(rows)]
