# Power Generation Mix

Generation mix is a power-system fundamental source product. It records
aggregate generation by fuel category for a market operator and delivery
interval. It does not represent unit-level generation, outage state, topology,
emissions, or settlement prices.

## Source Separation

`GenerationMixObservation` preserves the source publication row with:

- market operator and location;
- canonical fuel ID and raw source fuel label;
- delivery start and end in UTC;
- MW, optional percentage-of-total, renewable flag, and lineage.

Raw fuel labels are normalized only through `power_generation_fuels.yaml`.
Unknown labels fail closed. Source renewable flags must agree with the canonical
fuel registry.

PJM Data Miner `gen_by_fuel` may publish `Storage` as a fuel type. The canonical
fuel registry treats it as the `storage` family and non-renewable unless a
future approved source contract proves a different treatment for a specific
operator/source.

## PJM Implementation

The first approved source feed is PJM Data Miner `gen_by_fuel`. Its source fields
are registered in `power_generation_mix_feeds.yaml` and normalized into the
`pjm_generation_mix` artifact.

This approves aggregate PJM fuel mix only. It does not approve individual
generator output, outage lifecycle semantics, emissions conversion, or topology
links.

## Analyst View Consumption

Generation mix artifacts may include view-ready context fields such as
`summary`, `drivers`, `current_day_view`, and `evidence`. These fields are
derived only from the accepted `pjm_generation_mix` artifact and are consumed
through `HotState` by analyst views.

Screens and view builders must not call PJM Data Miner or the generation-mix
adapter directly. If generation mix is absent from the accepted state, the view
must remain schema-valid with explicit missing or empty context rather than
creating synthetic generation values.
