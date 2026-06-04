# Power + Gas Analytics Agent Build Packet v0.1

## Purpose

Build a local, model-agnostic Power + Gas Trading Analytics workbench. The system should normalize market indices, positions, marks, vol surfaces, periods, strips, spreads, and exposures into canonical, deterministic, auditable artifacts.

The durable artifact is not a chatbot prompt. It is a repository containing:

- domain rules
- schemas
- registries
- deterministic analytics code
- skills
- agent role definitions
- workflows
- evals/tests
- change-control rules

A new LLM or coding agent should be able to read this repository and begin improving the system without relying on prior chat history.

## Scope v0.1

### Power

Primary focus is PJM-centric eastern interconnect power, with initial locations:

- WH: PJM Western Hub
- AD: AEP-Dayton Hub
- NI: Northern Illinois Hub

Power prices use full LMP. Normalized records must delineate DA or RT. Bare power shorthand defaults to RT full LMP but must be displayed explicitly after normalization.

### Gas

Initial gas location/index universe:

- HH / Henry Hub
- TETCO-M3
- TETCO-M2
- Transco Z6 NNY
- Transco Z6 NY
- Transco Z5
- Transco Z5 South
- Eastern Gas South / Appalachia

Gas locations are grouped by pipe group and region. Recognized gas locations with no explicit index family default to GDD.

### Vol

MVP vol scope:

- Power: WH only
- Gas: HH only

Vol convention:

- Black-76 for v0.1
- ATM = true at-the-money strike for underlying contract settle
- skew = IV difference to ATM by delta bucket
- derive risk reversals and costless collar metrics

## Non-negotiable rules

1. Deterministic logic before agent reasoning.
2. Fail closed on ambiguity.
3. No market convention from LLM inference.
4. Every behavior-changing update needs tests.
5. Every convention-changing update needs a change request.
6. Spread notation is first/second = first - second.
7. Gas contract sizing is `.25/d` per contract, not `1.0/d` per contract.

## Implementation order

### Slice 1: semantic base

Build and test:

1. MarketIndex registry
2. PowerLocation registry
3. GasLocation registry
4. QuotedSpread registry
5. Period parser
6. ATC decomposer
7. Gas GDD default normalizer
8. PriceSurfacePoint normalizer
9. VolSurfacePoint normalizer for WH + HH
10. NormalizedPosition builder
11. Exception engine
12. Regression tests

### Slice 2: reconciliation and linear PnL

Inputs:

- prior normalized positions
- current normalized positions
- prior price surface
- current price surface

Outputs:

- position change report
- price change report
- linear PnL bridge
- driver ranking
- exception report

### Slice 3: vol and Greeks

Implement WH + HH vol surfaces, ATM IV curve, skew diff-to-ATM, risk reversals, costless collars, first-order Greeks, and vol move attribution.

### Slice 4: fundamentals

Add PJM/eastern power fundamentals, gas fundamentals, prior-day retrospective, current-day outlook, 14-day view, forecast-vintage archive, gas-day/power-day alignment.

### Slice 5: fair value and dashboard

Add fair-value bridges, rich dashboards, narrative generation, and recommendation-support artifacts.
