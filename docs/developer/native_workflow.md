# Native Workflow

GitHub is a plain remote. Do not use GitHub Actions, Issues, Projects, or PR
checks as workflow authority. Artemis owns validation, ticket lifecycle,
regression evidence, local-agent loops, and release readiness through native
repository commands.

Core commands:

```bash
make bootstrap
artemis validate --strict
artemis context audit
artemis work validate
artemis work show T-0030
artemis dev context --ticket T-0030 --output /tmp/T-0030_context.json
artemis dev loop --ticket T-0040 --backend manual --dry-run
artemis release check --ticket T-0030
```

`make validate` is a compatibility wrapper around `artemis validate`. Use
`artemis validate report --input ... --markdown ...` to bridge machine-readable
validation evidence into curated regression reports.

`artemis dev context` is the canonical context path. `pga work-context` is a
compatibility alias only and active wrapper prompts must call the Artemis command
directly. Tickets may request a configured `context_profile`; unknown profiles
fail closed.

Release readiness must fail when validation is skipped, stale, missing, tied to
the wrong ticket, non-strict, or disconnected from ticket lifecycle state. Coding
backends may propose patches, but deterministic Artemis checks decide readiness.
Strict validation includes context audit evidence for prompt, tool, skill, and
wrapper surface drift.

Semantic-impact tickets are gated before release readiness. Changes touching
domain docs, locked conventions, product or market registries, semantic schemas,
normalization, exposure, PnL, risk, units, periods, spreads, vol, or mapping
services must use the `trading_domain` or `behavioral` context profile. Release
readiness also requires strict validation evidence for pytest, registry/schema
validation, capability/lineage summaries, context audit, and a complete
affected-file snapshot. Convention-sensitive semantic changes require an
approved change request with affected files, required tests, and rollback plan.

Runtime tools must pass executable mode policy before they run. Analyst mode is
limited to read-only and workspace-output actions. Development repo writes
require a ticket, release-candidate tools require passed native validation
context, and convention-changing actions require approved change-request context.

Tool registry records carry command compatibility plus adapter, input/output
contract, lineage, authority, and deterministic-service metadata. Prompt-only or
candidate tools are never authoritative for PnL, risk, Greeks, forecasts, state,
mappings, or conventions.
