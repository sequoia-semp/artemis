# Gas Index Families

Supported v0.1 gas index families:

- GDD
- LD1
- IFERC
- BASIS_TO_LD1
- GDD_INDEX_TO_IFERC
- GDD_SWING
- CUSTOM

## Default

Recognized gas location with no explicit index family defaults to GDD.

## Formula conventions

Quoted spreads use first/second = first - second.

BASIS_TO_LD1 means regional monthly index minus Henry/LD1 only when the exact
official contract mechanics are verified by product spec or user-approved
convention before promotion. For the ICE gas demo grid, the approved formula is:

```text
Reference Price A - Reference Price B
A = regional Inside FERC monthly index
B = NYMEX Henry Hub natural gas settlement / Henry LD1
```

GDD_INDEX_TO_IFERC means average GDD daily price over the contract period minus
IFERC monthly index. For the ICE gas demo grid, the approved formula is:

```text
Average(Reference Price A prices) - Reference Price B
A = Gas Daily midpoint values for the contract period
B = regional Inside FERC monthly index
```
