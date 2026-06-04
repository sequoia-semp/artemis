# Regression Report v0.1

Execution date: 2026-06-04

Command executed from repository root:

```bash
make validate
```

Result:

```text
78 passed
validated 9 registry files; checked 34 records
validated 19 work items
validated knowledge base manifest with 4 entries
```

Covered invariant groups:

- Period grammar: PY, XH, JV, FG, NQ, quarter, calendar, BALMO.
- Power basis: allowed edges, forbidden edges, short spread leg exposure.
- Index normalization: bare power RT full LMP default, explicit DA peak, gas GDD default, explicit IFERC/LD1 overrides.
- Quantity conventions: gas `.25/d` per contract, 1.0/d = 4 contracts, total MMBtu, power MW to MWh.
- ATC and vol: equal MW peak/offpeak decomposition, hour-weighted ATC blended price, WH/HH vol MVP scope, skew diff-to-ATM, risk reversal.
- Registry-driven normalization: power locations, gas aliases, and quoted spreads are loaded from YAML registries with temp-registry regression coverage.
- Release workflow: deterministic release-check command, PJM MVP planning bridge files, and Python 3.11+ package metadata.

Limitations:

- Registry YAML validation is implemented for current registry files, but schemas remain intentionally permissive for early MVP evolution.
- Product master official-source ingestion is not implemented yet.
- Full position/mark normalization, PnL bridge, dashboard, and fundamentals workflows are future slices.
