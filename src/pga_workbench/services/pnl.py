from __future__ import annotations

from ..exceptions import VALUATION_INSUFFICIENT_DATA, VALUATION_TIE_OUT_FAILED, WorkbenchException
from ..models import NormalizedPosition, PnlAttributionReport

PNL_RESIDUAL_TOLERANCE = 1e-9


def _index(positions: list[NormalizedPosition]) -> dict[str, NormalizedPosition]:
    return {position.position_id: position for position in positions}


def _q(position: NormalizedPosition | None) -> float:
    if position is None:
        return 0.0
    return float(position.derived.get("valuation_quantity") or 0.0)


def _price(position: NormalizedPosition | None) -> float:
    if position is None:
        return 0.0
    mark = position.normalized.get("mark")
    if mark is None:
        raise WorkbenchException(VALUATION_INSUFFICIENT_DATA, f"PnL position {position.position_id} is missing mark")
    return float(mark)


def _value(position: NormalizedPosition | None) -> float:
    if position is None:
        return 0.0
    market_value = position.derived.get("market_value")
    if market_value is None:
        raise WorkbenchException(VALUATION_INSUFFICIENT_DATA, f"PnL position {position.position_id} is missing market_value")
    return float(market_value)


def _identity(position: NormalizedPosition | None) -> dict[str, object]:
    if position is None:
        return {}
    return dict(position.identity or {})


def _portfolio_value(positions: dict[str, NormalizedPosition]) -> float:
    return sum(_value(position) for position in positions.values())


def _residual_cause(residual: float, tolerance: float) -> str:
    return "within_tolerance" if abs(residual) <= tolerance else "bridge_exceeds_tolerance"


def _assert_bridge_tie_out(independent_total: float, explained_total: float, residual: float, tolerance: float) -> None:
    bridge_total = explained_total + residual
    tie_out_error = bridge_total - independent_total
    if abs(residual) > tolerance or abs(tie_out_error) > tolerance:
        raise WorkbenchException(
            VALUATION_TIE_OUT_FAILED,
            (
                "PnL bridge exceeds tolerance: "
                f"independent_total={independent_total}, explained_total={explained_total}, "
                f"residual={residual}, tie_out_error={tie_out_error}, tolerance={tolerance}, "
                f"residual_cause={_residual_cause(residual, tolerance)}"
            ),
        )


def _group_breakdowns(drivers: list[dict[str, object]]) -> list[dict[str, object]]:
    totals: dict[tuple[str, str], dict[str, object]] = {}
    for driver in drivers:
        identity = dict(driver.get("identity") or {})
        tags = identity.get("tags") or []
        group_values = {
            "book": identity.get("book"),
            "strategy": identity.get("strategy"),
            "portfolio": identity.get("portfolio"),
            "sleeve": identity.get("sleeve"),
        }
        for dimension, raw_value in group_values.items():
            if raw_value is None or raw_value == "":
                continue
            key = (dimension, str(raw_value))
            item = totals.setdefault(
                key,
                {
                    "dimension": dimension,
                    "value": str(raw_value),
                    "price_move_effect": 0.0,
                    "position_change_effect": 0.0,
                    "total_effect": 0.0,
                    "residual": 0.0,
                },
            )
            for field in ["price_move_effect", "position_change_effect", "total_effect", "residual"]:
                item[field] = float(item[field]) + float(driver[field])
        for tag in tags if isinstance(tags, list) else []:
            key = ("tag", str(tag))
            item = totals.setdefault(
                key,
                {
                    "dimension": "tag",
                    "value": str(tag),
                    "price_move_effect": 0.0,
                    "position_change_effect": 0.0,
                    "total_effect": 0.0,
                    "residual": 0.0,
                },
            )
            for field in ["price_move_effect", "position_change_effect", "total_effect", "residual"]:
                item[field] = float(item[field]) + float(driver[field])
    return sorted(totals.values(), key=lambda item: (str(item["dimension"]), str(item["value"])))


def run_pnl_attribution(
    prior_positions: list[NormalizedPosition],
    current_positions: list[NormalizedPosition],
    run_id: str = "pnl-run",
) -> PnlAttributionReport:
    prior = _index(prior_positions)
    current = _index(current_positions)
    position_change_effect = 0.0
    price_move_effect = 0.0
    drivers: list[dict[str, object]] = []
    independent_total = _portfolio_value(current) - _portfolio_value(prior)

    for position_id in sorted(set(prior) | set(current)):
        p0 = prior.get(position_id)
        p1 = current.get(position_id)
        q0 = _q(p0)
        q1 = _q(p1)
        price0 = _price(p0)
        price1 = _price(p1)
        price_effect = q0 * (price1 - price0)
        position_effect = (q1 - q0) * price1
        total_effect = _value(p1) - _value(p0)
        residual = total_effect - price_effect - position_effect
        price_move_effect += price_effect
        position_change_effect += position_effect
        drivers.append(
            {
                "position_id": position_id,
                "instrument_id": (p1 or p0).position_lot.get("instrument_id") if (p1 or p0) else None,
                "identity": _identity(p1 or p0),
                "price_move_effect": price_effect,
                "position_change_effect": position_effect,
                "total_effect": total_effect,
                "residual": residual,
            }
        )

    total_residual = sum(float(driver["residual"]) for driver in drivers)
    explained_total = (
        price_move_effect
        + position_change_effect
        + 0.0  # basis_move_effect
        + 0.0  # strip_weight_effect
        + 0.0  # atc_component_effect
        + 0.0  # mark_adjustment_effect
    )
    _assert_bridge_tie_out(independent_total, explained_total, total_residual, PNL_RESIDUAL_TOLERANCE)
    current_as_of = current_positions[0].as_of if current_positions else ""
    prior_as_of = prior_positions[0].as_of if prior_positions else ""
    return PnlAttributionReport(
        run_id=run_id,
        prior_as_of=prior_as_of,
        current_as_of=current_as_of,
        position_change_effect=position_change_effect,
        price_move_effect=price_move_effect,
        basis_move_effect=0.0,
        strip_weight_effect=0.0,
        atc_component_effect=0.0,
        mark_adjustment_effect=0.0,
        unexplained_residual=total_residual,
        bridge_sums=abs(total_residual) <= PNL_RESIDUAL_TOLERANCE,
        drivers=drivers,
        independent_total_effect=independent_total,
        explained_total_effect=explained_total,
        residual_tolerance=PNL_RESIDUAL_TOLERANCE,
        residual_cause=_residual_cause(total_residual, PNL_RESIDUAL_TOLERANCE),
        group_breakdowns=_group_breakdowns(drivers),
    )
