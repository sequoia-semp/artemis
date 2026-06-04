# Market Index Model

Every price is an observation on a named market index.

A `MarketIndex` includes:

- commodity
- location
- grouping hierarchy
- index family
- market run if power
- price component if power
- shape
- quote unit
- formula if spread/composite
- defaulting flags
- verification status

Spreads are also market indices when represented as first-minus-second formulas.

Power location grouping:

```text
ISO / balancing area -> hub/location -> DA/RT -> FULL_LMP -> shape
```

Gas location grouping:

```text
pipe group -> region -> location/index point -> index family
```
