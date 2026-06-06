# Regression Report T-0120

## Scope

Added a typed `RiskFactorId` for historical VaR exposure/scenario joins and
fail-closed construction for malformed factor inputs.

## Tests

- `.venv/bin/python -m pytest tests/golden -q` - passed, 8 tests.
- `.venv/bin/python -m pytest tests/test_workbench_mvp.py tests/test_price_instrument_spine.py -q` - passed, 23 tests.
- `.venv/bin/artemis validate --strict --ticket T-0120` - passed.

## Result

The calendar-spread golden case now exercises a non-trivial typed two-factor VaR
join, and malformed factor inputs fail before scenario PnL is computed.
