# Artemis

Artemis is a local, model-agnostic Power + Gas Trading Analytics workbench. The
durable product is the repository: deterministic Python services, domain
conventions, schemas, registries, skills, view templates, tests, and agent-mode
tooling.

`artemis` is the user-facing agent CLI. `pga` remains the lower-level deterministic
analytics command family and compatibility surface.

## Start Here

1. Read `AGENTS.md`.
2. Inspect `artemis.yaml`.
3. Use `docs/README.md` as the docs index.
4. Run validation:

```bash
make validate
artemis capabilities
```

Primary orientation files:

- `README.md`: product overview and first commands.
- `AGENTS.md`: canonical coding-agent contract.
- `llms.txt`: compact model/agent navigation index.
- `artemis.yaml`: central config, mode, tool, manifest, and release map.
- `docs/README.md`: user, analyst, developer, integration, and design-record index.

Historical build-packet and wrapper docs are archive/design records. They do not
override `AGENTS.md`, `artemis.yaml`, locked domain conventions, schemas,
registries, or tests. Domain convention details live in `domain/`,
`docs/CONVENTIONS_LOCKED_v0.1.md`, and regression tests.

## Core Commands

```bash
make bootstrap
make validate

artemis config validate
artemis capabilities
artemis skill validate
artemis views validate
artemis data-sources validate
```

Analyst Mode:

```bash
artemis analyst view build --template current-day --input tests/fixtures/views/current_day_minimal.json --output /tmp/current_day_view.json
```

Development Mode:

```bash
artemis dev context --ticket T-0019 --output /tmp/T-0019_context.json
artemis dev plan --ticket T-0019
artemis release check --ticket T-0019
```

Compatibility:

```bash
pga validate-registries
pga validate-work-items
pga validate-kb
pga work-context --ticket T-0019 --output /tmp/T-0019_context.json
```

## Mode Boundaries

Analyst Mode may produce workspace outputs such as views, reports, and summaries.
It must not mutate canonical repo files, update locked conventions, approve
mappings, publish shared state, or submit trades.

Development Mode is ticket-gated and validation-gated. Coding backends and model
providers are optional descriptors only; they are not authoritative for market
conventions, deterministic calculations, cache/state promotion, or release
approval.

## Current Status

| Area | Status |
|---|---|
| Artemis config and CLI | present |
| Deterministic `pga` analytics CLI | present |
| Locked conventions | present |
| Registry/schema validation | present |
| Analyst view engine | schema-backed skeleton |
| Data-source descriptors | descriptor-only, no live proprietary calls |
| Development context | Artemis config-backed |
| Release candidate workflow | deterministic, human-review required |
| TUI | deferred |
| Live vendor/ISO/ICE APIs | deferred until docs and credentials exist |

## Non-Authority Rules

Prompt-only analytics are not authoritative. PnL, risk, Greeks, forecasts, state
packs, cache behavior, mappings, and conventions must come from deterministic
services, reviewed registries/schemas, and tests.
