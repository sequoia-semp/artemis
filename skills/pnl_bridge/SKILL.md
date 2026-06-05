# Skill: PnL Bridge

## Purpose
Bridge D/D economic changes after semantic normalization is stable.

## Components v0.2 target
- position_change_effect
- price_move_effect
- basis_move_effect
- strip_weight_effect
- ATC_component_effect
- mark_adjustment_effect
- option_delta_effect
- option_gamma_effect
- option_vega_effect
- option_theta_effect
- unexplained_residual

## Rule
PnL bridge must sum. Residual must remain explicit.
Book, strategy, portfolio, sleeve, and tag groupings are inherited from
PositionLot metadata and must not change the bridge math.
