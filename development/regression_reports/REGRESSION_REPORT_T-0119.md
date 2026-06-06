# Regression Report T-0119

## Scope

Changed historical VaR to fail closed on missing valuation inputs and unmatched
risk-factor joins.

## Tests

- `.venv/bin/python -m pytest tests/golden -q` - passed, 2 tests.
- `.venv/bin/python -m pytest tests/test_workbench_mvp.py tests/test_price_instrument_spine.py -q` - passed, 23 tests.
- `.venv/bin/artemis validate --strict --ticket T-0119` - passed.

## Result

The golden missing-factor regression confirms VaR no longer defaults unmatched
factors to zero exposure.
