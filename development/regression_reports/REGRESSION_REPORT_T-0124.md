# Regression Report T-0124

## Scope

Validated PJM Data Miner runtime rate overrides against the account-class tier
budget.

## Tests

- `.venv/bin/python -m pytest tests/test_pjm_dataminer_connector.py -q` - passed, 20 tests, 2 skipped live tests.
- `.venv/bin/python -m pytest tests/test_source_query_plans.py -q` - passed, 14 tests.
- `.venv/bin/artemis validate --strict --ticket T-0124` - passed.

## Result

An over-budget `non_member` override fails closed before Data Miner request
planning proceeds, while lower overrides remain allowed.
