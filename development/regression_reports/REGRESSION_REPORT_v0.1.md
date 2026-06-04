# Regression Report v0.1

Execution date: 2026-06-04

Command executed from repository root:

```bash
python -m pytest -q
```

Result:

```text
22 passed
```

Covered invariant groups:

- Period grammar: PY, XH, JV, FG, NQ, quarter, calendar, BALMO.
- Power basis: allowed edges, forbidden edges, short spread leg exposure.
- Index normalization: bare power RT full LMP default, explicit DA peak, gas GDD default, explicit IFERC/LD1 overrides.
- Quantity conventions: gas `.25/d` per contract, 1.0/d = 4 contracts, total MMBtu, power MW to MWh.
- ATC and vol: equal MW peak/offpeak decomposition, hour-weighted ATC blended price, WH/HH vol MVP scope, skew diff-to-ATM, risk reversal.

Limitations:

- Registry YAML validation against JSON schemas is not implemented yet.
- Product master official-source ingestion is not implemented yet.
- Full position/mark normalization, PnL bridge, dashboard, and fundamentals workflows are future slices.
