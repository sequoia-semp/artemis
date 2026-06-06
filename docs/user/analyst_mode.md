# Analyst Mode

Analyst Mode is for deterministic market views, reports, explanations, and workspace outputs.
It reads approved schemas, registries, skills, and view templates. It may not mutate canonical
repo files, update locked conventions, approve mappings, publish shared state, or submit trades.

Initial view command:

```bash
artemis analyst view build --template current-day --input tests/fixtures/views/current_day_minimal.json --output /tmp/current_day_view.json
```

To build from the accepted state referenced by a local state root, pass
`--state-root`. Supplied input JSON still wins on conflicts. If no input JSON is
provided, the command uses the accepted state pack `as_of` date and builds from
HotState artifacts directly. Accepted HotState artifacts can provide drivers,
evidence, source lineage, scenarios, and view inputs:

```bash
artemis analyst view build --template current-day --state-root /path/to/state_root --input /tmp/current_day_input.json --output /tmp/current_day_view.json
```

```bash
artemis analyst view build --template current-day --state-root /path/to/state_root --output /tmp/current_day_view.json
```

When the accepted state contains a `power_system_artifact_bundle`, Analyst views
project compact source-audit metadata into the view `evidence` array. This can
include preflight status, metadata verification counts, source-readiness counts,
source-publication status, raw-fetch manifest counts, and operational-event
candidate-plan blockers. The projection is read-only and redacted; views do not
call PJM adapters or read raw source rows.

The same accepted bundle evidence can be inspected directly:

```bash
artemis analyst bundle source-audit --state-root /path/to/state_root --output /tmp/source_audit.json --allow-blockers
```

Or from a workspace bundle JSON:

```bash
artemis analyst bundle source-audit --bundle /tmp/pjm_morning_bundle.json --output /tmp/source_audit.json --allow-blockers
```

`--allow-blockers` returns success while preserving blocker details in the audit
report. Without it, blocked source readiness, candidate publications, or
unapproved operational-event plans produce a non-zero command result.

Fixture or test data is blocked in normal Analyst Mode unless explicitly enabled for validation.

Forward price heatmap:

```bash
artemis analyst heatmap build --input /tmp/price_surface_points.json --as-of 2026-06-04 --output /tmp/forward_price_heatmap.json
```

The heatmap can also read accepted `price_surface_points` through HotState:

```bash
artemis analyst heatmap build --state-root /path/to/state_root --as-of 2026-06-04 --output /tmp/forward_price_heatmap.json
```

The HotState read path exposes accepted price points through query helpers that
separate source-published price points from derived shape products. Analyst and
UI code should use those helpers instead of calling PJM adapters or reading raw
source rows.

HotState also exposes accepted fundamental records through query helpers that
separate source-specific products from best-series products. PJM load actuals,
load forecasts, forecast revisions, and generation mix observations should be
read from accepted HotState artifacts, not from PJM adapters inside Analyst or
UI code.

Explicit coverage gaps are also available through HotState helpers. Analysts
should surface these gaps as missing source-backed data, not fill them with
synthetic values.

The heatmap reports current prices with 1d, 5d, 10d, and 30d history deltas from
the power-system retention policy.
