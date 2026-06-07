# Regression Report: T-0152

## Ticket

T-0152 - Gas portfolio oracle and local LLM test surface

## Summary

Implemented a deterministic synthetic Henry Hub portfolio report and query
surface for a first local LLM user test. The report includes through-time linear
gas futures positions, registered ICE PHE option positions, Black-76
screening-only option metrics, linear PnL bridge output, option PnL, book PnL,
and LLM-ready supported/unsupported query responses.

Synthetic data is explicitly labeled `synthetic_test_fixture` and is not an
authoritative cache product.

## Files Changed

- `development/change_requests/CR-0103-gas-portfolio-local-llm-test.yaml`
- `docs/analyst/gas_portfolio_local_llm_test.md`
- `registries/tools.yaml`
- `src/pga_workbench/cli.py`
- `src/pga_workbench/services/gas_portfolio.py`
- `tests/test_gas_portfolio.py`
- `work/tickets/T-0152-gas-portfolio-local-llm-test.yaml`

## Tests Run

```bash
.venv/bin/python -m pytest tests/test_gas_portfolio.py -q
.venv/bin/python -m pytest tests/golden tests/test_price_instrument_spine.py -q
.venv/bin/pga validate-work-items
.venv/bin/pga validate-registries
.venv/bin/artemis validate --strict --ticket T-0152 --output development/validation_reports/T-0152/latest.json
```

All commands passed.

## Generated Local Test Artifacts

- `local/gas_portfolio_sample.json`
- `local/gas_portfolio_answer_total_pnl.json`
- `local/gas_portfolio_answer_positions_20260603.json`
- `local/gas_portfolio_answer_latest_greeks.json`

## Cache/State Contract

No accepted state-pack, shared cache, or cache promotion contract changed.
Synthetic fixture outputs remain local-test artifacts only.
