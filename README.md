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

| Area | Status |
|---|---|
| Locked conventions | present |
| Registry validation | present, needs expansion |
| Period parser | present |
| Power/gas index normalization | present |
| Position/mark normalization | present, early |
| PnL attribution | early skeleton |
| Historical VaR | early skeleton |
| Black-76 Greeks | early skeleton, WH/HH vol guard |
| State packs | present, early |
| Dashboard | not implemented |
| Fundamentals | models only / fixture ingestion only |
| Local LLM harness | present, local-context scaffold only |
| Work management | present, repo-native YAML work items |

## Next slice

After the semantic base passes tests, implement D/D position and mark reconciliation, linear PnL bridge, largest-driver ranking, and exception reports.
