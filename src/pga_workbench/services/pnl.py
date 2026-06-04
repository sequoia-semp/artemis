from __future__ import annotations

from ..models import NormalizedPosition, PnlAttributionReport


def _index(positions: list[NormalizedPosition]) -> dict[str, NormalizedPosition]:
    return {position.position_id: position for position in positions}


def _q(position: NormalizedPosition | None) -> float:
    if position is None:
        return 0.0
    return float(position.derived.get("valuation_quantity") or 0.0)


def _price(position: NormalizedPosition | None) -> float:
    if position is None:
        return 0.0
    return float(position.normalized.get("mark") or 0.0)


def _value(position: NormalizedPosition | None) -> float:
    if position is None:
        return 0.0
    return float(position.derived.get("market_value") or 0.0)


def run_pnl_attribution(
    prior_positions: list[NormalizedPosition],
    current_positions: list[NormalizedPosition],
    run_id: str = "pnl-run",
) -> PnlAttributionReport:
    prior = _index(prior_positions)
    current = _index(current_positions)
    position_change_effect = 0.0
    price_move_effect = 0.0
    drivers: list[dict[str, float | str]] = []

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
                "price_move_effect": price_effect,
                "position_change_effect": position_effect,
                "total_effect": total_effect,
                "residual": residual,
            }
        )

    total_residual = sum(float(driver["residual"]) for driver in drivers)
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
        bridge_sums=abs(total_residual) < 1e-9,
        drivers=drivers,
    )
