# Power System Source Catalog

The source catalog is the cross-source intake layer for direct ISO/RTO power
system data. It describes authoritative publication families before any feed is
promoted into a normalized contract, metric, price surface, best-series product,
or analyst view.

This layer is intentionally broader than PJM. A catalog record names the market
operator, access surface, product family, source feed names, contract families,
canonical roles, query-planning constraints, source terms, and verification
status. PJM Data Miner is the first concrete implementation because it is the
current MVP source of record, but the schema is not PJM-only.

## Promotion Rule

A catalog record may list candidate source feed names before a normalized feed
descriptor exists. An approved core record must reference existing feed
descriptors through `registry_feed_ids`. This prevents a source URL from
silently becoming an approved normalized product.

## Publication Lifecycle

The catalog also records generic power-system publication lifecycle semantics.
These fields are intentionally not PJM-specific:

- `cadence`: expected publication cadence such as hourly, event-driven,
  effective-dated, or mixed;
- `market_day_basis`: whether the source aligns to an operating day, calendar
  day, effective date, or is not applicable;
- `publication_finality`: whether the source is final, preliminary, revisioned,
  row-versioned, effective-dated, mixed, or still candidate-pending;
- `revision_policy`: whether revisions are absent, separated into latest and
  history products, row-versioned with a current-row filter, effective-dated, or
  unresolved;
- `retention_alignment`: how the source should align with hot, warm, cold, or
  candidate-only artifact retention;
- `authoritative_use`: whether the publication can support approved source
  artifacts or is only candidate metadata.

Approved core source publications must not carry unresolved lifecycle values.
This keeps source authority separate from source discovery: a feed can be
cataloged before it is safe to publish into accepted state.

Approved source catalog status means only:

- the publication family is an accepted source surface;
- the listed normalized feed descriptors exist and validate;
- query planning, timestamp policy, lifecycle semantics, terms, and source
  documents are registered.

It does not approve new pnodes, metrics, price components, outage lifecycle
semantics, topology links, best-series behavior, or shared-cache publication.
Those still require their own registries, contracts, tests, and change requests.

## Access Policies

Source access policy is registered separately from publication semantics in
`power_system_source_access_policies.yaml`. A policy captures row-count limits,
pagination defaults, account-class connection budgets, archive-planning notes,
and source terms.

Adapters must fail closed when a live query violates an approved access policy.
For PJM Data Miner this means:

- `rowCount` is bounded at 50,000;
- `startRow` is one-based;
- pagination defaults to one page;
- unbounded pagination is rejected;
- planned pages cannot exceed the account-class connection budget.

This keeps source access constraints executable without promoting additional
feed semantics.

## Query Execution Records

Approved source query plans produce deterministic request records before a live
adapter call is made. A request record includes the registry feed ID, source feed
name, request kind, pnode ID, date window, bounded pagination settings, query
parameters, and query-plan lineage.

For PJM hourly LMPs, the first executable plan builds:

- one pnode metadata request per requested pnode;
- one source-row request per pnode, feed, and daily window;
- current-row filters from the price-feed contract;
- UTC delivery date ranges from the query-plan window;
- compact execution summaries marked `contains_secret_values: false`.

For PJM load and generation-by-fuel surfaces, registry-backed bounded interval
plans build one source-row request per selected feed over the requested
source-backed date window. The registry records the applicable feed IDs,
publication lineage, access policy, date-window mode, and required query
dimensions; the service code turns that generic plan into PJM Data Miner
requests. These plans preserve row-count limits, pagination bounds, feed IDs,
source feed names, UTC date ranges, area filters where the feed descriptor
defines them, and compact execution summaries. They are intentionally simpler
than hourly LMP plans because they do not expand pnodes or daily LMP windows.

Adapters execute these records through `DataRequest`; they do not decide date
chunking, current-row policy, pnode expansion, or request budgets.

## PJM Bent

PJM Data Miner records carry PJM-specific feed names and terms while preserving
generic power-system product families:

- load actual and forecast feeds map to `load`;
- pnode and DA/RT LMP feeds map to `pricing_node_master` and
  `locational_marginal_price` semantics;
- generation-by-fuel is approved as an aggregate fuel-mix source product;
- outage, five-minute LMP, and transmission constraint feeds remain candidate
  expansion records until exact normalized contracts are added.

This keeps PJM first in implementation while avoiding a PJM-only concept model.
