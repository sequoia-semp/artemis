# Regression Report T-0132

## Scope

Added provider provenance to `RunManifest` and required persisted state-pack
manifests to include provider profile, provider kind, model-call flag, and
parameter provenance.

## Tests

- `.venv/bin/python -m pytest tests/test_release_readiness_native_validation.py -q` - passed, 13 tests.
- `.venv/bin/python -m pytest tests/test_workbench_mvp.py tests/test_power_system_state.py -q` - passed, 38 tests.

## Result

Run manifests now default to deterministic provider provenance and state-pack
schema validation requires that provenance in persisted manifests.
