# Regression Report T-0155

Ticket: T-0155
Change request: CR-0106
Status: passed

## Scope

Implemented a cached daily synthetic gas risk pack for the sample natural gas
portfolio. The pack materializes exposure buckets, historical VaR/expected
shortfall, deterministic stresses, option PnL explain, query facts, definitions,
lineage, and strategy semantics.

Strategy and structure names such as `straddle`, `costless_collar`, `25d_rr`,
and `breakeven` are advisory reporting labels only. `XH`, `JV`, and month codes
remain governed by `domain/period_grammar.md`. No option structure label was
promoted to an approved market convention.

## Generated Evidence

- `local/gas_portfolio_sample.json`
- `local/gas_risk_pack_20260603.json`
- `local/gas_risk_pack_20260603_cached.json`
- `local/gas_risk_answer_var_es.json`
- `local/gas_risk_answer_stress.json`
- `local/gas_risk_answer_strategy_semantics.json`
- `local/gas_risk_llm_stress_dry_run.json`

The first risk-pack build returned `cache_status=rebuilt`; the second build
returned `cache_status=hit`.

## Tests

- `.venv/bin/python -m pytest tests/test_gas_risk_pack.py -q` passed, 5 tests.
- `.venv/bin/python -m pytest tests/test_gas_risk_pack.py tests/test_gas_portfolio.py tests/test_valuation_ports_local_llm.py tests/test_oss_port_adapters.py tests/test_knowledge_base.py -q` passed, 24 tests.
- `.venv/bin/pga validate-registries` passed.
- `.venv/bin/pga validate-work-items` passed.
- `.venv/bin/artemis validate --strict --ticket T-0155 --output development/validation_reports/T-0155/latest.json` passed.

## Cache / State Contract

No authoritative cache or Morning State Pack contract changed. The risk pack is
a local synthetic daily artifact under a caller-selected output root and is
reused only when its manifest cache key matches.

## Known Gaps

The VaR/ES returns and stress grid are synthetic fixture metrics for local
diagnostics. Production source-backed returns, human-approved option structure
conventions, and authoritative shared-cache publication remain out of scope.
