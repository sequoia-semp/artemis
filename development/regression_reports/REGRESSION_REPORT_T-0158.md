# Regression Report T-0158

Ticket: T-0158
Change request: CR-0109
Status: passed

Implemented daily gas risk history over cached risk packs, including latest row,
VaR series, stress series, cache status, and daily pack paths.

Tests:
- `.venv/bin/python -m pytest tests/test_gas_integration.py -q`

Cache/state contract: no authoritative cache changed; only caller-selected local
risk-pack output roots are used.
