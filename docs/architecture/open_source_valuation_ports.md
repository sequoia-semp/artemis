# Open Source Valuation Ports

Artemis can use open-source pricing, risk, optimization, or research packages
only behind canonical ports. Package-native types must not leak into domain
models, report schemas, or agent tools.

## Current Built-Ins

- `pricing.black76_builtin`: deterministic Black-76 screening analytics.
- `risk.historical_var_builtin`: deterministic historical VaR.

These built-ins remain authoritative because they are covered by the golden
valuation suite.

## Optional Candidates

The adapter catalog tracks optional OSS candidates:

- `pricing.quantlib_black76_candidate`
- `risk.riskfolio_candidate`
- `risk.cvxportfolio_candidate`
- `risk.skfolio_candidate`

Use:

```bash
artemis analyst valuation-adapters --output local/valuation_adapters.json
```

Candidate adapters are non-authoritative until they are installed, wrapped
behind `PricingPort` or `RiskPort`, and oracle-validated. If requested before
promotion, they must fail closed.

## Promotion Gate

To promote an OSS adapter:

1. Keep all package-specific logic in an adapter module.
2. Accept canonical Artemis inputs and return canonical Artemis outputs.
3. Add golden scenarios proving agreement with hand-derived or trusted oracle
   values.
4. Label model scope, package version, and implementation lineage.
5. Keep the built-in deterministic implementation available as a regression
   baseline.

LLMs and local model wrappers may narrate adapter outputs only after the
deterministic tool has produced them.
