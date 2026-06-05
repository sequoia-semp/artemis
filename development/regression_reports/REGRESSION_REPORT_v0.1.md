# Regression Report v0.1

Execution date: 2026-06-05

Command executed from repository root:

```bash
make validate
```

Result:

```text
198 passed
validated 16 registry files; checked 157 records
validated 28 work items
validated knowledge base manifest with 4 entries
validated artemis config artemis 0.2.0
validated 7 skills
validated 6 view templates
validated 4 data sources
artemis capabilities passed with 19 registered tools
```

Covered invariant groups:

- Period grammar: PY, XH, JV, FG, NQ, quarter, calendar, BALMO.
- Power basis: allowed edges, forbidden edges, short spread leg exposure.
- Index normalization: bare power RT full LMP default, explicit DA peak, gas GDD default, explicit IFERC/LD1 overrides.
- Quantity conventions: gas `.25/d` per contract, 1.0/d = 4 contracts, total MMBtu, power MW to MWh.
- ATC and vol: equal MW peak/offpeak decomposition, hour-weighted ATC blended price, WH/HH vol MVP scope, skew diff-to-ATM, risk reversal.
- Registry-driven normalization: power locations, gas aliases, and quoted spreads are loaded from YAML registries with temp-registry regression coverage.
- Release workflow: deterministic release-check command, PJM MVP planning bridge files, and Python 3.11+ package metadata.
- Forward/fundamental mapping: ICE PJM power futures and ICE gas futures resolve to canonical MarketIndex records with lineage and formula-preserving mappings.
- Runtime/setup hardening: Artemis config, optional local model descriptors, state-pack schema checks, and forward price heatmap validation.
- Price instrument spine: ICE PMI, P1X, and PHE option descriptors validate; position lots preserve reporting metadata; exposure records carry grouping fields; PnL rollups group by book, strategy, portfolio, sleeve, and tags; registered option Greeks include contract metadata and scope flags.

Limitations:

- Some schemas remain intentionally permissive for early MVP evolution, but option contracts, exchange contracts, position lots, tools, work items, and data-source descriptors are schema-backed.
- Live ICE, vendor, ISO, cache publishing, and state-pack promotion remain descriptor/test scope unless credentials and source-policy controls are added.
- Option Greeks are Black76 screening analytics. American-style PMI exercise optionality is flagged and not modeled.
- Full trade-capture lifecycle, realized PnL, margin, confirmations, and counterparty/accounting dimensions remain outside the current scope.
