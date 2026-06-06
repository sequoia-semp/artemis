# Power System Price Source Model

This model separates generic power-system price observations from the first
PJM Data Miner implementation.

## Boundaries

`PowerSystemPriceFeed` describes a source feed from an ISO/RTO or balancing
authority. It is source-specific and may expose fields that are not canonical
tradable prices.

`PjmPnode` records official PJM pricing-node master data. It can verify a local
power location mapping, but it does not define trader-facing conventions by
itself.

`PjmLmpObservation` records one source-backed PJM hourly LMP observation at a
pricing node. It preserves full LMP and source components.

`PriceSurfacePoint` remains the canonical normalized price artifact. For power,
it must use explicit DA or RT, price component, shape or granularity, quote unit,
source, source role, timestamp, and lineage.

## Source Product Contracts

Power-system price feed descriptors carry a `source_product_contract` before a
feed can be treated as an approved source product. The contract is generic and
records:

- observation role: metadata or source price observation;
- delivery-window policy: effective-dated metadata or UTC hourly delivery
  windows;
- pnode identity policy: official pnode master data or approved-location pnode
  promotion;
- component policy: not applicable or full LMP/source-component coverage;
- version policy: effective-dated or current-row filter required;
- canonical promotion policy: metadata verification only or approved pnode and
  component requirements.

Approved hourly LMP feeds must require UTC delivery starts, current-row version
filtering, row version numbers, full LMP plus congestion/loss/energy component
columns, and approved pnode mappings before source observations can become
canonical `PriceSurfacePoint` records.

Hourly delivery-window normalization is fail-closed. Approved hourly source
price rows must align to exact UTC hour starts. When a source also publishes a
local market-clock timestamp, the implementation must prove that local timestamp
maps to the same UTC instant before the row can become a source observation.
For PJM Data Miner, `datetime_beginning_ept` must match
`datetime_beginning_utc` under PJM Eastern Prevailing Time.

PJM pnode mappings are effective-dated metadata. Price-state builds must verify
that the official pnode master record for an approved power location is active
for the artifact `as_of` timestamp before source LMP observations are promoted
to canonical price-surface points. Expired or not-yet-effective pnode metadata
fails closed.

## Source Versus Canonical Products

Direct ISO/RTO source products and canonical trading products are separate:

- Source LMP observations preserve pnode fields, row versioning, and all
  source-published LMP components.
- Canonical source price surfaces may include source-published `FULL_LMP`,
  `CONGESTION`, `MARGINAL_LOSS`, and `SYSTEM_ENERGY` components when the feed
  descriptor explicitly supports them.
- Trading products and forward mappings remain `FULL_LMP` unless separately
  approved. Source component products do not create exchange-settled component
  contracts.
- Hourly PJM LMP observations can become hourly `PriceSurfacePoint` records only
  for approved power locations with verified pnode mappings.
- Peak, off-peak, ATC, monthly, strip, and forward shapes must be derived by
  calendar services and explicit settlement rules, not by source adapter logic.
  Daily PEAK, OFFPEAK, and ATC rollups are handled by
  `power_price_shape_rules.yaml` and the deterministic shape-rollup service.
  Shape rollups currently consume hourly `FULL_LMP` points only; component
  rollups require their own approved rules.

## PJM First Implementation

The first implementation uses PJM Data Miner feeds:

- `pnode` for official pricing-node master data
- `da_hrl_lmps` for day-ahead hourly LMPs
- `rt_hrl_lmps` for real-time hourly LMPs

The generic contract is broader than PJM, but PJM is the only approved
source-backed implementation in this pass.

`rt_fivemin_hrl_lmps` is registered only as a candidate five-minute real-time
LMP source surface. Its interval, version, retention, and canonical promotion
semantics are not approved. Candidate descriptors and query plans may support
metadata review and future planning, but five-minute source rows cannot be
normalized into `PjmLmpObservation` or promoted into canonical
`PriceSurfacePoint` artifacts in this pass.

## History And Heatmap Scope

PJM hourly LMP artifacts are approved as source-restorable history through the
hourly LMP daily chunk query plan. The retention policy explicitly supports the
1d, 5d, 10d, and 30d heatmap windows while keeping hourly DA/RT source rows,
canonical hourly price-surface points, and derived shape/heatmap products
separate.

Heatmap builders may read ad hoc file input for tests and local analysis, but
the production analyst read path should consume accepted `price_surface_points`
through `HotState`.
