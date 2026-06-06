# Power System Ingestion Bundles

This document describes deterministic power-system artifact bundles. It does
not approve new source feeds, locations, price components, or state-pack publish
behavior.

## Purpose

Direct source ingestion produces separate source-specific and derived artifacts.
A bundle composes those artifacts into one workspace JSON payload that can be
validated, inspected, and passed to the existing state-pack build path.

The bundle layer is intentionally generic:

- source artifacts remain separate products;
- derived artifacts keep deterministic lineage;
- composition metadata is preserved;
- bundle metadata records operator, source system, as-of time, environment, and
  composition product keys.
- optional preflight evidence is stored in redacted form.
- optional source metadata verification evidence is stored in compact redacted
  form.
- optional source readiness evidence is stored in compact redacted form.
- source publication lifecycle evidence is stored in compact redacted form.
- live raw source fetch manifests may be stored as non-product evidence without
  raw source rows or credential values.
- optional operational-event candidate-plan evidence is stored in compact
  redacted form.

## PJM First Binding

The first bundle command is `build-pjm-morning-bundle`. It can build from
fixtures or opt-in live PJM Data Miner fetches. The bundle includes:

- PJM load fundamentals;
- PJM generation mix;
- PJM hourly DA/RT LMP prices;
- derived power price shape rollups.

Live fetches reuse the existing bounded Data Miner connector, source access
policy, query planning, and feed-specific normalizers.

Live PJM build paths also produce generic `raw_source_fetch_manifests` evidence
for each source request. These manifests record request IDs, source surface,
registry feed IDs, source feed names, query-plan IDs, delivery windows, pnodes
where applicable, row/page counts, selected query field names, and a SHA-256
hash of the raw records received. They do not embed raw source rows, request
headers, subscription keys, or other credential values. Fixture-backed builds do
not synthesize raw fetch manifests.

When a bundle contains `raw_source_fetch_manifests`, bundle metadata also
contains compact `raw_source_fetches` evidence. The summary records manifest
counts, total row/page counts, truncation counts, source-surface counts,
registry feed IDs, query-plan IDs, and per-request hashes. It must remain
redacted: neither raw source rows nor credential values may appear in bundle
metadata. Pipeline reports surface the compact counts when present so source
review can confirm what was fetched without inspecting raw rows.

Live PJM bundles generate preflight evidence before fetching source
observations. If the preflight is not ready, the bundle fails before live source
fetches begin. Fixture-backed bundles may attach a prior preflight report with
`--preflight-input`; `--require-ready-preflight` enforces the same ready gate.
Bundle metadata preserves both the legacy single `query_plan` evidence field and
the generic `query_plans` mapping keyed by source surface, such as load, price,
and generation mix. The embedded query-plan evidence is compact and redacted:
plan IDs, request counts, account class, windows, and lineage may be retained,
but raw debug fields, request headers, and credential values are not bundle
metadata.

Live PJM bundles also verify selected PJM Data Miner feed definitions before
fetching source observations. The bundle stores only compact evidence: feed IDs,
definition source, observed/required field counts, and a secret-free flag. It
does not store raw source definition payloads. Fixture-backed bundles may attach
the same evidence with `--metadata-input`; `--require-metadata-verification`
requires that evidence for offline bundle builds.

PJM bundles may also attach a prior power-system source readiness report with
`--source-readiness-input`. The input report must validate against the generic
source readiness schema before the bundle is written. When
`--require-ready-source-readiness` is supplied, blocked readiness evidence fails
the bundle build before live source observations are fetched. Bundle metadata
stores only compact readiness evidence: ready flag, blocker count, source-fetch
statuses, counts, and error codes. It does not store raw source rows, request
headers, or credential values. If the readiness report includes query execution
evidence, bundle metadata preserves only the compact redacted summary: plan ID,
request counts, account class, request kinds, selected feed IDs, pnode IDs, date
windows, and `contains_secret_values: false`.

PJM bundles also attach compact source publication evidence derived from the
generic source catalog for the selected load, pnode, LMP, and generation feeds.
This evidence records publication IDs, status, feed IDs, canonical roles, and
publication lifecycle semantics. Candidate source publications remain visibly
candidate in the bundle metadata and are not promoted into approved state-pack
publish behavior by their presence in the evidence.

PJM bundles can also attach the generic operational-event candidate plan with
`--include-operational-event-plan` or a validated prior report supplied through
`--operational-event-plan-input`. The embedded evidence records publication and
feed blockers for outages and constraints, including pending timestamp,
identifier, normalization, lifecycle, and topology approval. It does not fetch
operational-event source rows, normalize outage or constraint records, create
topology links, populate HotState, or authorize state-pack publication.
`--require-approved-operational-events` fails closed when the attached plan is
not approved, which is the expected current PJM state.

## State-Pack Boundary

The bundle command writes workspace JSON only. It does not publish accepted
state. Publishing remains a separate explicit state-pack operation so candidate
validation, synthetic-data blocking, shared-readonly blocking, and atomic
accepted-state pointer swaps stay centralized in the state package.

`stage-power-system-bundle-candidate` and
`artemis analyst bundle stage-state-candidate` can turn a validated bundle into
a candidate state pack. These commands validate the bundle and build only under
the candidate state directory. They do not update `current.json`, move the
candidate into accepted state, or bypass the existing publish guardrails.

`run-pjm-morning-pipeline` combines bundle build and candidate staging for the
PJM morning artifact set. It is still candidate-only: the output bundle and
pipeline report are workspace files, and accepted-state publish remains a
separate operation.

## Source Audit

`power-system-source-audit` and `artemis analyst bundle source-audit` build a
standalone read-only audit report from either a workspace bundle JSON or the
accepted state exposed through HotState. The report is generic power-system
metadata: it summarizes preflight, metadata verification, source readiness,
source publications, raw source fetch manifests, and operational-event
candidate-plan blockers. It does not call source adapters, inspect raw source
rows, alter state packs, or publish cache/state.
