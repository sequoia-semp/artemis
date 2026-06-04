# Fundamental Views

The Fundamental View Engine is the Analyst Mode path for structured market/fundamental views.
It replaces a separate research-agent tree with schema-backed view templates under `views/`.

Initial templates:

- `current_day`
- `prior_day_retrospective`
- `fourteen_day_fundamentals`
- `eastern_power_market`
- `gas_basis_market`
- `forecast_actual_delta`

Released views must make missing inputs explicit and preserve evidence, source lineage, and
data-quality fields.
