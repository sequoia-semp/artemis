# ATC Conventions

ATC is a composite of equal MW peak and off-peak.

```text
ATC = PEAK equal MW + OFFPEAK equal MW
```

Valuation:

```text
ATC value = MW * peak_hours * peak_price + MW * offpeak_hours * offpeak_price
```

Display price:

```text
ATC blended price = total_component_value / total_component_MWh
```

This applies to month, FG, NQ, quarter, calendar, planning year, BALMO, and custom strips.
