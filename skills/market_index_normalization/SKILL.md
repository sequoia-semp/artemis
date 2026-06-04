# Skill: Market Index Normalization

## Purpose
Normalize raw market labels into canonical MarketIndex records.

## Rules
1. Power uses full LMP.
2. Bare power location defaults to RT full LMP.
3. Gas recognized location defaults to GDD.
4. Do not infer unknown location.
5. Preserve raw text.
6. Store default flags.

## Required output
- MarketIndex
- defaulting flags
- structured exceptions
