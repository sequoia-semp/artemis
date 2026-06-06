# Power Price Shape Rules

Power-system price shapes are derived from hourly source observations by
registry-backed rules. The source adapter must not embed peak, off-peak, ATC,
holiday, or settlement math.

## Daily Scope

This slice supports daily rollups from hourly full-LMP price surface points:

- `PEAK`: hours ending 0800-2300 EPT on weekdays excluding NERC holidays.
- `OFFPEAK`: weekday hours ending 0100-0700 and 2400 EPT, plus all hours on
  weekends and NERC holidays.
- `ATC`: all hours in the power day.

The rollup output is a derived `PriceSurfacePoint`. It is not a new source row.
It must preserve lineage to the input hourly points and the rule ID used.

Shape rules reference power-market calendar IDs. Calendar definitions live in
`power_market_calendars.yaml`; services must resolve holiday membership through
that registry rather than standalone constants.

## Incomplete Days

An incomplete day does not produce an authoritative derived shape price by
default. The service emits an explicit gap with expected and observed hour
counts instead of filling or extrapolating.

## Analyst View Consumption

Price shape artifacts may include view-ready `summary`, `drivers`,
`current_day_view`, and `evidence` fields. These fields are derived from the
accepted `power_price_shape_rollups` artifact and its lineage to hourly
authoritative source prices.

Analyst screens and view builders must consume these fields through `HotState`.
They must not call the PJM adapter, re-run hourly rollups, fill incomplete days,
or infer unapproved price shapes in the read path.

## Future Scope

Monthly, strip, planning-year, BALMO, and exchange-settlement products should
reuse these daily/hourly rule primitives, but they require a fuller calendar and
retention pass before promotion.
