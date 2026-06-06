# Power System Artifact Retention

This document describes the power-system artifact retention layer. It does not
override source policy, artifact product registration, state-pack immutability,
or forecast-retention guardrails.

## Scope

Retention policy is registered by artifact product key in
`power_system_artifact_retention_policies.yaml`. The registry is generic to
power-system artifacts and currently binds PJM as the first implementation.

The policy layer answers four questions before source-backed products are
allowed into accepted state:

- whether the artifact may publish to a state pack;
- whether lineage is mandatory;
- whether source-specific products must remain separate;
- which hot, warm, and cold retention behavior applies.
- which approved source-query plans can restore historical source products for
  derived views.

## PJM First Binding

PJM load fundamentals, PJM hourly LMP prices, PJM generation mix, and derived
power price shape rollups are approved for state-pack publish when their
artifact schemas and source lineage validate.

Operational event feed descriptors remain candidate-only. They may be described
in registries and tests, but they cannot publish to accepted state until outage,
constraint, lifecycle, and topology semantics are approved.

## Forecast Retention

Load latest forecast curves and historical forecast revisions are separate
physical and semantic products. Latest curves are hot. Recent 6h/12h revisions
are hot/warm. Older exact revisions are cold/source-restorable unless explicitly
restored into an analysis run.

Do not collapse revision history into a latest-curve product for convenience.

## Price History Retention

PJM hourly LMP history is source-restorable through the approved hourly LMP
query plan. The source product stays separate from derived price-shape and
heatmap products. The approved hot history horizon is 30 days, matching the
1d, 5d, 10d, and 30d heatmap windows. Historical LMP rows retain the current-row
filtering requirement from the source price feed contract.

## Historical Source Router

Historical source routing is policy-driven. A router may build compact,
non-fetching request plans only for artifacts whose retention policy marks them
`source_restorable` and names approved query plans. The first implementation
binds PJM artifacts to their approved Data Miner query planners:

- `pjm_power_prices` routes hourly DA/RT LMP history through daily LMP chunks
  and preserves the 1d, 5d, 10d, and 30d windows.
- `pjm_load_fundamentals` routes approved load forecast feeds through the
  bounded load query plan. Candidate actual-load feeds are not included by
  default.
- `pjm_generation_mix` routes generation-by-fuel history through the bounded
  generation mix query plan.

The router does not fetch source rows, mutate cache, or publish state. It emits
only request evidence: artifact key, history window, approved query-plan IDs,
request counts, compact request descriptors, and a secret-free flag.

## Publish Guardrail

Every artifact product must have exactly one retention policy. Native validation
fails closed when:

- a product is missing a retention policy;
- a policy references an unknown product or operator;
- product family, commodity, operator, or publish status disagree;
- a publishable product does not require lineage;
- a publishable source product does not require source-specific separation;
- a candidate product is marked publishable.
- a source-restorable historical policy does not name an approved query plan;
- a derived view window exceeds the approved hot history horizon;
- PJM hourly LMP history does not retain the approved query plan, heatmap
  windows, or row-version policy.
