# Regression Report T-0129

## Scope

Required analyst-view quantitative claims and structured display figures to
resolve to source lineage. Source lineage entries now receive stable
`lineage_id` values, quantitative claim lineage is recorded in `data_quality`,
and structured display objects receive or require `lineage_ref`.

## Tests

- `.venv/bin/python -m pytest tests/test_analyst_views.py -q` - passed, 13 tests.
- `.venv/bin/python -m pytest tests/test_pjm_fundamentals_semantic_core.py -q` - passed, 11 tests.

## Result

Views now fail with `VIEW_ERROR` when grounded quantitative claims or displayed
numeric driver figures lack resolvable lineage references.
