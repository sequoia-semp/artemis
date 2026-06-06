# Direct PJM Authoritative Sources

This plan describes the next incorporation layer for direct PJM data. It does
not approve new conventions by itself; implementation still requires source
descriptors, schemas, fixtures, tests, and change requests.

## Objectives

Direct PJM source support should make PJM official publications first-class
inputs for both fundamentals and prices while preserving the workbench safety
model:

- PJM Data Miner is the authoritative ISO publication path for approved PJM
  source feeds.
- Source-specific products remain separate from best-series products.
- Latest forecast curves remain separate from forecast revision history.
- Price publications remain separate from derived shapes and forward-product
  mappings.
- Raw source fetch evidence is compact, redacted, and auditable.
- Textual and Analyst views read through HotState artifacts, not adapters.
- Failed readiness, metadata, normalization, validation, or publish checks
  preserve the prior accepted state.

## Current State

The repository already has most control-plane pieces needed for a broader PJM
pass:

- Data Miner connector scaffolding with credential redaction and optional live
  smoke behavior.
- Approved and candidate source-publication catalog entries for PJM load,
  hourly LMP, pnodes, generation mix, five-minute LMP, outage, and operational
  event feeds.
- Metadata expectation validation for registered Data Miner feed definitions.
- Query-plan descriptors for bounded load, generation mix, hourly LMP, and
  candidate planning surfaces.
- Raw source fetch manifests and source-audit reports that summarize fetch
  lineage without embedding raw rows.
- Publication gates that block candidate source publications in production
  bundles.
- HotState projection of source evidence into Analyst views.
- Retention-backed historical source request routing for approved
  source-restorable artifacts.
- A load-only live pipeline that can fetch the approved seven-day load forecast
  feed, verify source metadata, build source-readiness evidence, stage a
  candidate state pack, and publish through the production source-publication
  gate.

This means the next expansion should focus on normalization depth and promotion
policy, not on bypassing the existing evidence path.

## Source Domains

### Fundamentals

Approved fundamentals should start with load and generation mix because they
already have source descriptors and deterministic fixture coverage. Load actual,
preliminary actual, latest forecast, and forecast revision history must remain
distinct physical and semantic products until a best-series policy explicitly
selects a view series.

Candidate or untested feed semantics should not populate authoritative
FundamentalState artifacts. They may appear in source-audit or planning evidence
with candidate labels and blockers.

### Prices

PJM hourly day-ahead and real-time LMP publications are authoritative price
inputs only after pnode identity, effective dates, timestamp windows, and
component semantics validate. Hourly LMP source points may feed derived daily
shape products and forward heatmap history, but those derived products must
carry lineage back to the source publication and the shape rule.

Five-minute LMP remains candidate-only until its source fields, retention
policy, downstream use, and promotion gates have dedicated tests.

## Work Decomposition

1. Source readiness hardening:
   make Data Miner feed-definition checks and query-plan blockers the first
   preflight gate for any live or fixture-backed PJM pull.

2. Source row normalization:
   extend fixture-backed normalization for approved fundamentals and hourly
   LMPs with strict timestamp, area, pnode, unit, and quality handling.

3. Artifact contracts:
   keep source-specific observations, forecast snapshots, price points,
   derived shapes, best-series products, and view bundles as separate contracts.

4. Promotion path:
   publish only validated artifact bundles through candidate state pack directories and atomic accepted-state pointer swaps.
   Approved production source publications must have matching source-readiness,
   metadata-verification, and raw-fetch evidence for the selected registry
   feeds before publish can update the accepted-state pointer.

5. HotState read path:
   expose accepted fundamentals, hourly prices, derived shapes, source audit
   evidence, and explicit gaps through HotState query/view services. Price
   reads must preserve the distinction between source-published price points
   and derived shape products. Fundamental reads must preserve the distinction
   between source-specific products, best-series products, forecast revision
   history, and generation mix observations. Gap reads must preserve explicit
   missing-source evidence rather than implying synthetic fills.

6. Analyst and UI integration:
   build deterministic view models from HotState artifacts before adding
   narrative summaries or Textual screens.

## User Decisions Needed

- Which PJM source feeds move from candidate to approved next, by feed ID and
  product use.
- Which PJM pnodes and load areas are in MVP scope beyond the already verified
  hub identities.
- Whether five-minute LMP is needed for MVP views or can remain candidate-only.
- Whether generation mix should be included in the morning summary before
  outage/topology work.
- The first live-smoke operating cadence and acceptable Data Miner request
  window sizes.
- The state root and cache deployment mode for local-only versus shared
  authoritative state.

## High-Risk Areas

- Timestamp interpretation across UTC and PJM Eastern Prevailing Time.
- Forecast vintage retention accidentally collapsing latest curves and revision
  history.
- Pnode identity drift or effective-date mismatch for price points.
- Treating candidate source publications as approved production inputs.
- Losing source/product separation when building best-series views.
- Raw rows or credentials leaking into state packs, audit reports, logs, or
  committed fixtures.
- UI or Analyst paths calling adapters directly instead of HotState.
- Derived price shapes being mistaken for PJM-published price products.

## Next Implementation Slices

- Add stricter fixture normalization tests for approved PJM hourly LMP feeds,
  including delivery windows and pnode effective-date enforcement.
- Add a source-readiness gate that blocks publish when requested approved feeds
  lack matching metadata verification and raw-fetch manifests.
- Extend HotState query helpers for accepted source-specific price points and
  derived daily shape products.
- Add Analyst views that compare source audit evidence, accepted fundamentals,
  and price lineage without fetching PJM directly.
- Expand the load-only pipeline to approved actual-load feeds only after their
  source contracts move out of candidate status.
