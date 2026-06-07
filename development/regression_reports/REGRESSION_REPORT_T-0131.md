# Regression Report T-0131

## Scope

Added deterministic provider-profile enforcement to Artemis config validation.
The default provider must be deterministic; model-backed deterministic defaults
must explicitly guarantee determinism, pin `temperature` to `0`, and pin `seed`
when supported.

## Tests

- `.venv/bin/python -m pytest tests/test_artemis_config.py tests/test_release_readiness_native_validation.py -q` - passed, 24 tests.

## Result

Non-deterministic default provider configs now fail with `ARTEMIS_CONFIG_ERROR`.
The native default remains `deterministic_only`, and optional model profiles
remain available as non-authoritative descriptors.
