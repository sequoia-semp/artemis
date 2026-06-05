# Change Policy

## Change classes

- Class 0: documentation only
- Class 1: examples or test additions
- Class 2: registry addition without behavioral change
- Class 3: new parser behavior
- Class 4: schema extension
- Class 5: valuation/exposure logic change
- Class 6: source hierarchy or convention change
- Class 7: workflow change

Class 3+ requires a change request. Class 5+ requires regression comparison before promotion.

## Semantic-change gate

Before core engine or mapping-semantics work is promoted, release readiness treats
the following as semantic-impact surfaces:

- domain convention files and locked convention docs
- product, market, period, quantity, spread, vol, and fundamental mapping registries
- schemas for positions, exposures, price surfaces, PnL, periods, market indices, products, and vol surfaces
- deterministic parser, normalization, exposure, PnL, risk, units, periods, spreads, and vol services

Semantic-impact tickets must use the `trading_domain` or `behavioral` context
profile, carry deterministic regression tests, and pass strict native validation
with registry/schema, capability/lineage, pytest, and context-audit evidence.
Convention-sensitive registry or domain changes also require approved
change-request metadata with affected files, required tests, and rollback plan.
