# Regression Report T-0123

## Scope

Added bounded retry/backoff handling for PJM Data Miner `429` / `Retry-After`
throttle responses.

## Tests

- `.venv/bin/python -m pytest tests/test_pjm_dataminer_connector.py -q` - passed, 18 tests, 2 skipped live tests.
- `.venv/bin/artemis validate --strict --ticket T-0123` - passed.

## Result

The connector honors a simulated `Retry-After`, sleeps through the injectable
hook, retries, and succeeds. A separate regression confirms exhausted retry
budget fails closed.
