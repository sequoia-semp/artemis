# Regression Report T-0118

## Scope

Added independent PnL bridge tie-out against begin/end MTM totals and a
fail-closed breach path for attribution mismatches.

## Tests

- `.venv/bin/python -m pytest tests/golden -q` - passed, 5 tests.
- `.venv/bin/python -m pytest tests/test_workbench_mvp.py tests/test_price_instrument_spine.py -q` - passed, 23 tests.
- `.venv/bin/artemis validate --strict --ticket T-0118` - passed.

## Result

The golden injected-bug regression confirms the PnL bridge raises
`VALUATION_TIE_OUT_FAILED` when bucket attribution no longer ties to the
independent portfolio MTM total.
