# Regression Report T-0127

## Scope

Hardened PJM Data Miner payload parsing so unexpected non-list envelopes are
rejected rather than wrapped as a single record.

## Tests

- `.venv/bin/python -m pytest tests/test_pjm_dataminer_connector.py -q` - passed, 21 tests, 2 skipped live tests.
- `.venv/bin/artemis validate --strict --ticket T-0127` - passed.

## Result

Malformed non-list envelopes now fail closed with `PJM_DATAMINER_ERROR`.
