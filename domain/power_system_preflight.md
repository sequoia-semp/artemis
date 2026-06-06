# Power System Ingestion Preflight

This document describes non-mutating ingestion preflight checks for direct
power-system source workflows.

## Purpose

Preflight reports identify whether a source-backed ingestion run is ready before
fetching live data or building state-pack candidates. A preflight may inspect
configuration, registry selections, source access policy, metadata expectations,
and query plans, but it does not fetch source observations and does not publish
state.

## PJM First Binding

The first preflight implementation is PJM Data Miner. It reports:

- whether `ARTEMIS_PJM_API_KEY` is configured, without exposing the value;
- selected PJM load, price, pnode, and generation mix feeds;
- source metadata expectations for selected feeds;
- PJM Data Miner source access limits;
- bounded load, hourly LMP, and generation mix query-plan request counts;
- readiness blockers.

The report is ready only when credentials are configured, a date window is
present, at least one pnode/location is selected for LMP planning, and the
planned request count fits the configured account-class budget.

Preflight retains the legacy `query_plan` field for hourly LMP compatibility
and also emits `query_plans` keyed by selected source surface. `load` and
`generation_mix` entries come from approved bounded interval query-plan records
and are evidence only; preflight still does not fetch source rows.

## Boundary

Preflight does not approve candidate feeds, infer source semantics, write shared
cache, publish state packs, or run live data pulls. It is an operator-facing
gate before metadata verification and source ingestion.

## Live Smoke

`pjm-live-smoke` and `artemis data-sources pjm-live-smoke` produce a redacted
direct-source readiness artifact. The artifact validates against the generic
`power_system_source_readiness` schema. The smoke path reuses preflight planning,
verifies selected PJM Data Miner definitions, and, unless `--metadata-only` is
supplied, fetches one bounded page with one row per selected source surface:

- load;
- pnode metadata;
- hourly LMP;
- generation mix when enabled.

Smoke reports contain counts, statuses, feed IDs, and redacted credential flags.
They do not store raw source rows, request headers, API keys, accepted-state
artifacts, or cache writes. A smoke report is evidence that the configured
source path is reachable for a narrow sample; it is not a state-pack publish
operation and does not approve new source semantics.

When a smoke report fetches source rows, it may include compact query execution
evidence from the approved source query plan. For the current PJM hourly LMP
path this records the plan ID, built versus planned request count, account
class, connection budget, request kinds, selected feed IDs, pnode IDs, date
windows, and `contains_secret_values: false`. It does not include API keys,
request headers, or raw source rows.

Each source-row check is recorded independently. If one selected surface times
out or returns a structured source error, the report records a redacted per-feed
error item and marks the smoke report not ready instead of crashing before the
artifact can be inspected.

The schema is intentionally operator-neutral: it requires an operator ID, source
system, readiness flag, blockers, redacted preflight evidence, compact metadata
verification evidence, per-source fetch statuses, and an explicit
`contains_secret_values: false` flag. PJM Data Miner is the first producer of
this contract, not the only intended source system.

## Bundle Evidence

PJM morning bundles may embed preflight evidence in bundle metadata. The embedded
evidence is redacted and records readiness, blocker count, selected feeds,
credential configured flags, and query-plan context. It must not contain raw API
keys or other secret values.
