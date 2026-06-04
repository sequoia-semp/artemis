# Units and Quantities

## Power

Power raw quantity defaults to MW. MWh is derived.

```text
derived_MWh = signed_MW * reference_hours
value = signed_MW * reference_hours * USD_per_MWh
```

## Gas

Gas exchange contract sizing uses `.25/d` per contract.

```text
1 contract = 0.25/d = 2,500 MMBtu/day
1.0/d = 4 contracts = 10,000 MMBtu/day
total_MMBtu = signed_contracts * 2500 * delivery_days
value = total_MMBtu * USD_per_MMBtu
```

Canonical convention ID:

```text
ICE_GAS_CONTRACT_0_25D_EQUIVALENT
```

Do not use `1 contract = 1.0/d`.
