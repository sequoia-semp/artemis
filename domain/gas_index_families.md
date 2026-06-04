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

BASIS_TO_LD1 generally means regional index minus Henry/LD1, but exact official contract mechanics must be verified by product spec or user-approved convention before promotion.

GDD_INDEX_TO_IFERC means average GDD daily price over the contract period minus IFERC monthly index.
