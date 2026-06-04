# artemis

Artemis is a local, model-agnostic Power + Gas Trading Analytics workbench. It is intended to be handed to a coding agent, file-system-aware LLM, or human developer as a self-contained starting point.

The packet is not a production trading system. It is a scaffold containing locked domain conventions, schemas, registries, starter code, tests, skills, agent role files, and an improvement protocol.

## Start here

1. Read `AGENTS.md`.
2. Read `docs/BUILD_PACKET_v0.1.md`.
3. Read `docs/CONVENTIONS_LOCKED_v0.1.md`.
4. Inspect `registries/` and `schemas/`.
5. Run tests from the repository root after installing the package in editable mode:

```bash
python -m pip install -e .[dev]
python -m pytest
```

## Critical correction baked into v0.1

Gas exchange contract sizing uses the `.25/d` convention:

```text
1 contract = 0.25/d = 2,500 MMBtu/day
1.0/d = 4 contracts = 10,000 MMBtu/day
total MMBtu = contracts × 2,500 × delivery days
```

Do not revert this to `1 contract = 1.0/d`.

## Current implementation status

- Domain architecture: included.
- JSON schemas: included.
- YAML registries: included.
- Starter Python modules: included.
- Starter pytest tests: included.
- Full PnL bridge/dashboard/fundamentals implementation: not included yet.

## Next slice

After the semantic base passes tests, implement D/D position and mark reconciliation, linear PnL bridge, largest-driver ranking, and exception reports.
