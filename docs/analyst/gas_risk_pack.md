# Gas Risk Pack

A Gas Risk Pack is a daily, materialized, synthetic local-test artifact built
from the sample gas portfolio report. Analyst and local LLM questions should
read the pack instead of recalculating history.

Build:

```bash
artemis analyst gas-risk build \
  --portfolio-report local/gas_portfolio_sample.json \
  --as-of 2026-06-03 \
  --output-root local/gas_risk_packs \
  --output local/gas_risk_pack_20260603.json
```

Query:

```bash
artemis analyst gas-risk query \
  --input local/gas_risk_pack_20260603.json \
  --question "What is 95% VaR and expected shortfall?" \
  --output local/gas_risk_answer_var.json
```

Local LLM narration:

```bash
artemis analyst gas-risk ask-local-llm \
  --input local/gas_risk_pack_20260603.json \
  --question "What is the worst stress scenario?" \
  --output local/gas_risk_llm_stress.json \
  --dry-run
```

The pack includes:

- manifest and cache key
- position snapshots
- exposure buckets by period and strategy
- historical VaR and expected shortfall
- deterministic stress scenarios
- option PnL explain with residual
- query index and metric definitions

The pack is synthetic and local-test only. It must not publish to authoritative
shared cache.
