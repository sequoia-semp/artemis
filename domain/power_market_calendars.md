# Power Market Calendars

Power-market calendars are first-class registry objects. Services may resolve
calendar rules, but adapters and screens must not hardcode holiday or shape
math.

## Current Scope

This pass registers:

- `NERC_HOLIDAYS`: the North American power holiday set referenced by current
  PJM/ICE peak and off-peak shape rules.
- `PJM_EPT_POWER_DAY`: the PJM Eastern Prevailing Time power day used for
  hourly Data Miner LMP shape rollups.

The calendar registry supports fixed-date, nth-weekday, and last-weekday holiday
rules. Observed holiday policy and exchange-specific ad hoc date overrides are
deferred until source-backed examples require them.

## Use In Shape Rules

`power_price_shape_rules.yaml` references a `holiday_calendar`. The rollup
service uses that calendar to decide whether a date is weekday, weekend, or
holiday before applying expected hour-ending sets.
