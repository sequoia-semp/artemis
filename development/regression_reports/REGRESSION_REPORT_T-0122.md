# Regression Report T-0122

## Scope

Added a token-bucket runtime limiter for PJM Data Miner requests and a
process-shared limiter registry keyed by account class and request budget.

## Tests

- `.venv/bin/python -m pytest tests/test_pjm_dataminer_connector.py -q` - passed, 16 tests, 2 skipped live tests.
- `.venv/bin/artemis validate --strict --ticket T-0122` - passed.

## Result

The simulated burst test confirms requests sleep through the limiter instead of
being rejected, and the shared-registry test confirms matching account-class
budgets reuse one limiter instance inside the process.
