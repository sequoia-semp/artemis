# Regression Report: T-0154

## Ticket

T-0154 - Open-source valuation port adapter catalog

## Summary

Added a deterministic adapter catalog for the valuation port layer. Built-in
Black-76 pricing and historical VaR are reported as available authoritative
ports. Optional OSS candidates for QuantLib, Riskfolio, cvxportfolio, and
skfolio are discovered without eager imports and reported as non-authoritative
candidate adapters until installed and oracle-validated.

Requesting the QuantLib candidate before promotion fails closed with a
structured `OSS_ADAPTER_UNAVAILABLE` or `OSS_ADAPTER_NOT_VALIDATED` exception.

## Files Changed

- `development/change_requests/CR-0105-oss-port-adapter-catalog.yaml`
- `development/regression_reports/REGRESSION_REPORT_T-0154.md`
- `docs/README.md`
- `docs/architecture/open_source_valuation_ports.md`
- `docs/architecture/power_gas_trading_agent_workbench.md`
- `registries/tools.yaml`
- `src/pga_workbench/cli.py`
- `src/pga_workbench/services/ports.py`
- `tests/test_oss_port_adapters.py`
- `work/tickets/T-0154-oss-port-adapter-catalog.yaml`

## Tests Run

```bash
.venv/bin/python -m pytest tests/test_oss_port_adapters.py tests/test_valuation_ports_local_llm.py -q
.venv/bin/pga validate-work-items
.venv/bin/pga validate-registries
.venv/bin/artemis validate --strict --ticket T-0154 --output development/validation_reports/T-0154/latest.json
```

All commands passed.

## Generated Artifact

- `local/valuation_adapters.json`

The current environment reports all optional OSS candidates unavailable because
`QuantLib`, `riskfolio`, `cvxportfolio`, and `skfolio` are not installed in the
venv. This is expected and fail-closed.

## Cache/State Contract

No accepted state-pack, shared cache, or cache promotion contract changed.
