# Regression Report T-0133

## Scope

Separated optional model-backed exploration from deterministic default Artemis
runs by marking `local_ollama` as `exploratory` and blocking exploratory
profiles as `providers.default_profile`.

## Tests

- `.venv/bin/python -m pytest tests/test_artemis_config.py -q` - passed, 12 tests.

## Result

Exploratory model profiles remain available as optional descriptors, but they
cannot be configured as the default deterministic Artemis profile.
