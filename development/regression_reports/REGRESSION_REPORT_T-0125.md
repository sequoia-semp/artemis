# Regression Report T-0125

## Scope

Added a constructive redaction scanner for power-system source evidence and
wired it into bundle validation, source audit checks, and source-publication
publish gates.

## Tests

- `.venv/bin/python -m pytest tests/test_power_system_ingestion.py tests/test_power_system_source_audit.py -q` - passed, 38 tests.
- `.venv/bin/python -m pytest tests/test_power_system_ingestion.py tests/test_power_system_source_audit.py tests/test_power_system_state.py -q` - passed, 58 tests.

## Result

Evidence that claims `contains_secret_values: false` now still fails if it
contains disallowed secret-bearing field names such as `api_key`. Redacted
credential status metadata remains allowed.
