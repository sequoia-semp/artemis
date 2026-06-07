# Regression Report T-0157

Ticket: T-0157
Change request: CR-0108
Status: passed

Implemented gas portfolio roll-up reconciliation for market value and PnL across
book, strategy, portfolio, and sleeve, with tag roll-ups labeled as
multi-allocation diagnostics.

Tests:
- `.venv/bin/python -m pytest tests/test_gas_integration.py -q`

Cache/state contract: unchanged.
