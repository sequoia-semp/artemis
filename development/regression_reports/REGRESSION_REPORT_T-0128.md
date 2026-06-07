# Regression Report T-0128

## Scope

Added a grounding pass to the analyst view engine for quantitative claims in
summary, stance, and driver narrative text. Numeric claims now need matching
numeric values in the non-narrative input/evidence/artifact payload.

## Tests

- `.venv/bin/python -m pytest tests/test_analyst_views.py -q` - passed, 10 tests.
- `.venv/bin/python -m pytest tests/test_analyst_views.py tests/test_pjm_fundamentals_semantic_core.py -q` - passed, 21 tests.

## Result

Unsupported numeric summaries now raise `VIEW_ERROR`; grounded numeric summaries
continue to build schema-valid view payloads.
