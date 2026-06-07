# Regression Report T-0130

## Scope

Added explicit analyst-view regressions for supported and unsupported
quantitative driver-text claims.

## Tests

- `.venv/bin/python -m pytest tests/test_analyst_views.py -q` - passed, 15 tests.

## Result

Grounded driver-text numbers build with lineage references, while unsupported
driver-text numbers fail with `VIEW_ERROR`.
