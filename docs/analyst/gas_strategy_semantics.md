# Gas Strategy Semantics

This file documents candidate reporting labels for the synthetic gas portfolio
risk example. It is advisory and requires human review before any label becomes
a market convention or valuation rule.

## Locked Period Grammar

These are already controlled by `domain/period_grammar.md`:

- `XH`: gas winter, November through March.
- `JV`: gas summer, April through October.
- Month codes: `F`, `G`, `H`, `J`, `K`, `M`, `N`, `Q`, `U`, `V`, `X`, `Z`.

## Candidate Reporting Labels

The following labels may appear in strategy or tag fields for grouping and
diagnostics only:

- `outright`
- `calendar`
- `vol`
- `straddle`
- `costless_collar`
- `25d_rr`
- `breakeven`

They do not change valuation, option exercise assumptions, strip weighting,
source mapping, risk-factor selection, or PnL explain logic.

## Human Review Gate

Before promotion to canonical behavior, each structure needs:

- exact instrument-leg definition
- orientation and quote convention
- units and premium treatment
- expiry and exercise assumptions
- regression tests with hand-derived expected values
- approval through a change request
