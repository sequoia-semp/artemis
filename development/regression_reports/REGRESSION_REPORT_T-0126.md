# Regression Report T-0126

## Scope

Wired PJM Data Miner definition fetching through the public `definition_url`
path instead of leaving it as unused connector code.

## Tests

- `.venv/bin/python -m pytest tests/test_pjm_dataminer_connector.py -q` - passed, 20 tests, 2 skipped live tests.
- `.venv/bin/artemis validate --strict --ticket T-0126` - passed.

## Result

Definition fetches now use `definition_url`, do not send API credentials, and
remain covered by connector unit tests.
