# Skill: Position Normalization

## Purpose
Normalize raw positions into canonical exposures.

## Rules
- Power raw quantities default to MW.
- Gas exchange-contract quantities use .25/d per contract.
- Preserve raw product, period, quantity, and mark.
- Do not value unknown products.
- Composite products must expose components.

## Required output
- NormalizedPosition
- ExposureRecord list
- ExceptionReport
