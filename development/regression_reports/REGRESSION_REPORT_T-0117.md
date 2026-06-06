# Regression Report T-0117

## Scope

Added an explicit required `golden_valuation` check to native validation.

## Tests

- `.venv/bin/python -m pytest tests/test_native_validation_runner.py tests/golden -q` - passed, 6 tests.
- `.venv/bin/artemis validate --strict --ticket T-0117` - passed.

## Result

No regressions found. Native validation reports `golden_valuation` as a required
passing check.
