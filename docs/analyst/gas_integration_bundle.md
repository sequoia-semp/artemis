# Gas Integration Bundle

The gas integration bundle is the deterministic end-to-end local-test artifact
for the natural gas portfolio oracle. It combines registry-derived contract
definitions, sample portfolio valuation, roll-up reconciliation, cached daily
risk history, hand-checkable risk oracle checks, diagnostics, and a grounded
narrative probe.

Build:

```bash
artemis analyst gas-integration build \
  --output local/gas_integration_bundle.json \
  --output-root local/gas_risk_packs \
  --registries registries \
  --force
```

The bundle success criteria are:

- roll-ups reconcile by book, strategy, portfolio, and sleeve
- risk oracle checks pass against deterministic hand calculations
- narrative probe is answered by the deterministic risk-pack query tool
- shared authoritative cache remains unchanged

The bundle is synthetic and local-test only. It must not publish to
authoritative shared cache, and it does not promote candidate strategy labels
to market conventions.
