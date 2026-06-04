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

## Local agent integration

Artemis supports local agent workflows, but deterministic services remain authoritative. The wrapper-neutral boundary is `pga work-context`: it packages repo guidance, locked conventions, change policy, ticket metadata, and affected files into a deterministic context bundle.

### 1. Prepare the repo

From the repo root:

```bash
make bootstrap
make validate
```

Generate a deterministic context bundle for a ticket:

```bash
make work-context TICKET=T-0006
```

The context bundle loads `AGENTS.md`, `llms.txt`, locked conventions, change policy, the ticket YAML, and files listed under the ticket's `affected_files`.

### 2. Optional wrappers

OpenCode is the first supported coding/review harness. Ollama is an optional local model runtime. OpenClaw is optional outer orchestration and should start with read-only Artemis commands only.

See:

- `docs/WRAPPER_ABSTRACTION_POLICY.md`
- `docs/AGENT_MODES.md`
- `docs/OPENCODE_SETUP.md`
- `integrations/`

Use `pga agent-capabilities` to inspect optional wrapper availability. Missing optional wrappers must not break Artemis core.

Use `pga vcs-ready --ticket T-####` or `make vcs-ready TICKET=T-####` before committing and pushing a ticket branch.

Use `pga validate-kb` or `make validate` to check the deterministic knowledge-base scaffold.

### 3. Release loop for KB, skills, and agents

Knowledge-base entries, skills, prompts, OpenCode agents, and wrapper configuration are released like code:

1. Create or select a ticket under `work/tickets/`.
2. Generate context with `pga work-context`.
3. Update KB, skills, prompts, agent config, code, or tests on a ticket branch.
4. Run:

   ```bash
   python -m pytest -q
   pga validate-registries
   pga validate-work-items
   ```

5. Merge into `main` only after review.
6. Tag releases when the validated baseline should be shared.

Prompt-only analytics are not authoritative. PnL, risk, Greeks, forecasts, state packs, and cache behavior must come from deterministic services and tests.

## Next slice

After the semantic base passes tests, implement D/D position and mark reconciliation, linear PnL bridge, largest-driver ranking, and exception reports.
