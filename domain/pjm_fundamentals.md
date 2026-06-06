# PJM Fundamentals Semantic Core

This file defines the current approved semantic slice for PJM power-system
fundamentals. It does not override locked market conventions, source policy,
registries, schemas, or tests.

## Scope

The current slice is PJM-only and load-first:

- hourly actual load
- hourly preliminary load
- seven-day latest load forecast
- historical load forecast revisions
- deterministic actual-minus-forecast load error

Outages, topology, gas, non-PJM regions, and new LMP/price semantics are out of
scope for this slice.

## Source Authority

PJM Data Miner is the source-backed path for this slice. Source-specific products
must remain separate from best-series products:

- source-specific metered load
- source-specific preliminary load
- source-specific latest forecast curve
- source-specific forecast revision history
- deterministic best actual load series

The latest forecast curve and historical revision products are separate physical
and semantic products. Do not collapse revision history into the hot latest
curve.

## Quality Rule

Metered load is preferred over preliminary load for best-series actual load.
Preliminary load may be used only with an explicit quality label and lineage
when metered load is unavailable.

Live PJM metadata for `hrl_load_prelim` exposes `load_area` as the area field.
It does not expose `zone` or `area` alternates, so the preliminary-load source
contract requires only `load_area` for area normalization. Metered load keeps
its broader source-observed area alternates.

## Load Actual Approval

PJM load actual feeds remain candidate until a source-feed approval report proves
all required promotion evidence. Metadata verification can prove that Data Miner
definitions expose the registry fields, but metadata alone does not approve a
feed for authoritative accepted-state use. Promotion also requires source-row
evidence for the feed and an approved source publication whose lifecycle allows
`approved_source_surface` authoritative use.

The current candidate actual-load publication is intentionally blocked from
production accepted-state publish by source publication gates. Fixture, test,
development, and local environments may still exercise the source-specific
normalizers and best-series rules without changing the authoritative registry
status.

## Gaps

The `+/-14d` view shape may be emitted before every day is source-backed. Missing
source-backed days must be explicit gaps. Do not fill gaps with synthetic or
inferred values.

## Fail-Closed Rule

Unknown feed IDs, load areas, delivery windows, timestamp fields, units, or
quality states must produce structured exceptions. Do not infer unsupported PJM
semantics from source names or model confidence.
