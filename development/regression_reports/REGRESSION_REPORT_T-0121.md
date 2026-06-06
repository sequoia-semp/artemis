# Regression Report T-0121

## Scope

Added explicit screening-only and vol-input scope labels to Black-76 Greeks
outputs and golden expectations.

## Tests

- `.venv/bin/python -m pytest tests/golden -q` - passed, 8 tests.
- `.venv/bin/python -m pytest tests/test_price_instrument_spine.py tests/test_workbench_mvp.py -q` - passed, 23 tests.
- `.venv/bin/artemis validate --strict --ticket T-0121` - passed.

## Result

Golden option cases reproduce known Greeks to tolerance and assert explicit
screening-only labels on row outputs and report lineage.
