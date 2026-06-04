# Skill: Price Surface Normalization

## Purpose
Normalize raw marks/settles/prices into canonical PriceSurfacePoint records.

## Rules
- Every price must have index_id, period_id, quote unit, source, source role, timestamp if available.
- Power must show DA/RT and FULL_LMP.
- Gas defaults to GDD when family is absent.
- Preserve raw lineage.

## Required output
- PriceSurfacePoint records
- exceptions
