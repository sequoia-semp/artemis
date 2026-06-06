# Power System Source Metadata Verification

This document describes source metadata verification for direct power-system
publications. It does not approve new source products, market conventions,
locations, or state-pack artifacts.

## Purpose

Direct source ingestion should fail before normalization when an authoritative
source definition no longer contains the fields required by registered feed
descriptors. The source metadata layer derives expected fields from normalized
feed registries and can compare them with source metadata payloads.

## Generic Shape

The concept is power-system wide:

- registry descriptors define required source fields;
- source metadata payloads expose observed source fields;
- verification compares required versus observed fields;
- missing required fields fail closed with a structured exception.

No source metadata check may infer unsupported feed semantics. It only proves
that required source columns still exist for already-registered descriptors.

## PJM First Binding

PJM Data Miner is the first implementation. Metadata expectations are derived
from:

- `pjm_fundamental_feeds.yaml`;
- `power_system_price_feeds.yaml`;
- `power_generation_mix_feeds.yaml`.

The approved core feeds currently include PJM load forecasts, hourly DA/RT LMP,
pnode metadata, and generation by fuel. Candidate outage, constraint, and
five-minute LMP publications remain outside approved metadata enforcement until
their normalized contracts are added.

## Native Validation

Native validation checks that approved source catalog feed IDs have metadata
expectations. Live network metadata fetches are intentionally opt-in and are not
part of default validation.

## Verification Command

`verify-pjm-source-metadata` and `artemis data-sources verify-pjm-metadata`
produce a verification report from either fixture metadata or opt-in live PJM
Data Miner definition fetches.

By default, the verifier selects approved core feed descriptors. Explicit
`--feed` selections may use Data Miner feed names or registry feed IDs.
`--include-candidate` is allowed for inspection, but it does not promote
candidate feeds or authorize state-pack publish.

Live verification uses the credentialed PJM Data Miner metadata API at
`/api/v1/{feed}/metadata`. The browser-oriented Data Miner definition page is a
UI reference, not the authoritative JSON source for automated verification.

The PJM morning bundle and candidate-only pipeline paths reuse this verifier.
Live runs verify the selected load, generation mix, hourly LMP, and pnode
metadata definitions before observation fetches. Offline fixture runs may pass
`--metadata-input`, and `--require-metadata-verification` fails closed when no
metadata verification input is supplied. Bundles retain only compact evidence,
not raw definition payloads.
