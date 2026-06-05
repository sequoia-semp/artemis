# Analyst Mode

Analyst Mode is for deterministic market views, reports, explanations, and workspace outputs.
It reads approved schemas, registries, skills, and view templates. It may not mutate canonical
repo files, update locked conventions, approve mappings, publish shared state, or submit trades.

Initial view command:

```bash
artemis analyst view build --template current-day --input tests/fixtures/views/current_day_minimal.json --output /tmp/current_day_view.json
```

To build from the accepted state referenced by a local state root, pass
`--state-root`. Supplied input JSON still wins on conflicts, but accepted
HotState artifacts can provide drivers, evidence, source lineage, scenarios, and
view inputs:

```bash
artemis analyst view build --template current-day --state-root /path/to/state_root --input /tmp/current_day_input.json --output /tmp/current_day_view.json
```

Fixture or test data is blocked in normal Analyst Mode unless explicitly enabled for validation.

Forward price heatmap:

```bash
artemis analyst heatmap build --input /tmp/price_surface_points.json --as-of 2026-06-04 --output /tmp/forward_price_heatmap.json
```

The heatmap expects normalized `PriceSurfacePoint` JSON and reports current
prices with 1d, 5d, 10d, and 30d history deltas.
