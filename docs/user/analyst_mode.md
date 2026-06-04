# Analyst Mode

Analyst Mode is for deterministic market views, reports, explanations, and workspace outputs.
It reads approved schemas, registries, skills, and view templates. It may not mutate canonical
repo files, update locked conventions, approve mappings, publish shared state, or submit trades.

Initial view command:

```bash
artemis analyst view build --template current-day --input tests/fixtures/views/current_day_minimal.json --output /tmp/current_day_view.json
```

Fixture or test data is blocked in normal Analyst Mode unless explicitly enabled for validation.
