# Locked Conventions v0.1

This file contains the current approved domain conventions. Do not change these without a change request.

## Universal spread notation

```text
FIRST/SECOND = FIRST price - SECOND price
```

The signed quantity controls economics.

Example:

```text
-25 MW WH/AD
```

means:

```text
spread = WH - AD
WH exposure = -25 MW
AD exposure = +25 MW
```

The system must not relabel this as AD/WH.

## Power price component

Power prices use full LMP. Basis is full LMP basis. Do not use congestion-only, loss-only, or energy-only components unless a future approved convention explicitly adds them.

## Power market run

Normalized power prices must explicitly state DA or RT.

Bare power index shorthand defaults to RT full LMP:

```text
WH N26 -> PJM.WH.RT.FULL_LMP.ATC.N26
```

The default flag must be stored.

## Approved power basis graph

Approved:

```text
WH/AD = WH - AD
AD/NI = AD - NI
WH/NI = WH - NI
WH/NI = WH/AD + AD/NI
```

Forbidden by default:

```text
AD/WH
NI/AD
NI/WH
```

If a forbidden orientation appears, produce `NON_CANONICAL_BASIS_ORIENTATION`. Do not silently transform.

## ATC

ATC is equal MW peak + equal MW off-peak.

```text
ATC value = MW × peak_hours × peak_price + MW × offpeak_hours × offpeak_price
ATC display price = total component value / total component MWh
```

This must work for monthly, FG, NQ, quarterly, calendar, planning-year, BALMO, and custom strips.

## Power quantities

Power preserves both MW and MWh.

```text
derived_MWh = signed_MW × reference_hours
value = signed_MW × reference_hours × price_USD_per_MWh
```

## Gas default index family

Recognized gas location with no explicit index family defaults to GDD.

```text
TETCO-M3 N26 -> GAS.TETCO_M3.GDD.DAILY.N26
```

Explicit labels override default:

```text
IFERC
LD1
basis
index
swing
```

## Gas quantity convention

Gas exchange sizing uses `.25/d` per contract.

```text
1 contract = 0.25/d = 2,500 MMBtu/day
1.0/d = 4 contracts = 10,000 MMBtu/day
total_MMBtu = contracts × 2,500 × delivery_days
```

Do not encode `1 contract = 1.0/d`.

## Period grammar

Month codes:

```text
F Jan, G Feb, H Mar, J Apr, K May, M Jun, N Jul, Q Aug, U Sep, V Oct, X Nov, Z Dec
```

Planning year:

```text
PY26 = Jun26-May27
```

Gas winter:

```text
X26H27 = Nov26-Mar27
```

Gas summer:

```text
JV27 = Apr27-Oct27
```

Power seasonal shorthand:

```text
FG26 = Jan26-Feb26
NQ26 = Jul26-Aug26
```

BALMO:

```text
BALMO always excludes the next-day product.
```

## Vol

MVP vol scope:

```text
WH and HH only
```

Model:

```text
Black-76
```

ATM:

```text
true at-the-money strike for underlying contract settle
```

Skew:

```text
IV difference to ATM
```
