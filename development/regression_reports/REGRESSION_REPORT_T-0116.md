# Regression Report T-0116

## Scope

Added hand-derived golden scenarios for a calendar spread and a registered
option position, extending the existing flat single-leg fixture.

## Tests

- `.venv/bin/python -m pytest tests/golden -q` - passed, 4 tests.
- `.venv/bin/artemis validate --strict --ticket T-0116` - passed.

## Result

No regressions found in the golden valuation scenario suite.
