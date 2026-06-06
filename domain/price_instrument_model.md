# Price Instrument, Position, Exposure, and PnL Model

This model is the price-centric spine for Artemis. It follows a lean ETRM/CTRM
shape while keeping market conventions deterministic and registry-backed.

## Artifact Boundaries

`MarketIndex` describes the canonical economic index. It is not a trade.

`ExchangeContract` describes listed futures, swaps, basis, spread, or index
contracts whose settlement rules are sourced from official exchange records.

`OptionContract` describes listed option classes on futures or index-like
underlyings. It is a contract descriptor, not a single strike/expiry position.

`PriceSurfacePoint` describes a normalized mark or settle for an index,
instrument, delivery period, source, and as-of timestamp.

Direct ISO/RTO source prices are source products before they become price
surfaces. For PJM, hourly Data Miner LMP observations preserve pnode, row
version, and component fields separately; only full-LMP observations for
approved pnode mappings may be promoted into canonical `PriceSurfacePoint`
records.

Daily PEAK, OFFPEAK, and ATC prices derived from hourly source points are
deterministic rollups. They must preserve the input hourly point IDs, shape-rule
ID, observed hour count, and any explicit source gaps.

`PositionLot` describes a held lot in a tradeable instrument, including
position-only grouping metadata.

`ExposureRecord` decomposes a position lot into valuation-ready economic
exposures. Composite products must expose component legs.

`PnLExplain` compares prior and current valuations and keeps residuals explicit.

`GreeksReport` values registered option rows with model inputs and returns
screening Greeks. It must preserve model scope and option style.

## Minimum Descriptors

Contract descriptors must carry enough information to resolve:

- tradeable symbol and venue
- commodity and location
- underlying index or contract
- contract period and delivery period
- contract size and quantity unit
- quote, premium, strike, and currency units
- settlement method and formula/reference price
- expiry or last trading day rule
- source documents and verification status

Price descriptors must carry:

- `index_id` or instrument reference
- `period_id`
- `as_of`
- price, quote unit, source, source role, and lineage

Position descriptors must carry:

- `position_id`
- `instrument_id`
- `instrument_type`
- signed quantity and quantity unit
- mark or mark reference
- raw product, raw period, raw quantity, source, and lineage

## Position Grouping Metadata

The following fields are optional and reporting-only:

- `book`
- `strategy`
- `portfolio`
- `sleeve`
- `structure_id`
- `tags`
- `metadata`

These fields may group, filter, and roll up positions, exposures, views, and PnL.
They must not change valuation, contract resolution, exposure decomposition,
calendar rules, option style, source mappings, or market convention semantics.

## Option Scope

The initial registered option universe is:

- ICE PMI: Option on PJM Western Hub Real-Time Peak (1 MW) Fixed Price Future
- ICE P1X: Option on PJM Western Hub Real-Time Peak Calendar Year One Time Fixed Price Future
- ICE PHE: Option on Henry Penultimate Fixed Price Future

MVP Greeks use Black76 screening analytics for WH and HH only. European options
are in-scope for standard Black76 screening. American-style options are flagged
as screening-only because early exercise optionality is not modeled.

Unknown options, unsupported vol locations, missing underlyings, missing strikes,
or missing model inputs must fail closed or return structured exceptions.

## PnL Explain

PnL explain outputs must include:

- price move effect
- position or quantity change effect
- basis/spread effects where available
- strip and ATC component effects where available
- option delta/gamma/vega/theta effects where available
- explicit unexplained residual
- group rollups by book, strategy, portfolio, sleeve, and tags

Residuals must remain visible. Grouping metadata is inherited from position lots.
