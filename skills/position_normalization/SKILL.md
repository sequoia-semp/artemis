# Skill: Position Normalization

## Purpose
Normalize raw positions into canonical exposures.

## Rules
- Power raw quantities default to MW.
- Gas exchange-contract quantities use .25/d per contract.
- Preserve raw product, period, quantity, and mark.
- Preserve reporting-only book, strategy, portfolio, sleeve, tags, and metadata.
- Do not value unknown products.
- Composite products must expose components.
- Reporting metadata must not alter valuation, mapping, calendar, or decomposition semantics.

## Required output
- NormalizedPosition
- PositionLot
- ExposureRecord list
- ExceptionReport
