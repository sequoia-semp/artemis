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

Artemis supports local agent workflows, but deterministic services remain authoritative. OpenCode is the primary coding/review harness. OpenClaw can be used later as an optional outer orchestration layer, but it should start with read-only Artemis commands.

### 1. Prepare the repo

From the repo root:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
pga validate-registries
pga validate-work-items
```

Generate a deterministic context bundle for a ticket:

```bash
pga work-context --ticket T-0006 --output /tmp/artemis_T-0006_context.json
```

The context bundle loads `AGENTS.md`, `llms.txt`, locked conventions, change policy, the ticket YAML, and files listed under the ticket's `affected_files`.

### 2. Configure OpenCode

OpenCode reads `opencode.jsonc` from this repo. The config is intentionally conservative:

- deterministic validation commands are allowed
- broad shell commands require approval
- `git push*` and `git tag*` require approval
- OpenCode is not part of runtime analytics or state/cache publishing

Start Ollama in a separate terminal:

```bash
ollama serve
```

Pull the local coding model if needed:

```bash
ollama pull qwen3-coder:30b
```

Run OpenCode against the repo:

```bash
opencode . --model ollama/qwen3-coder:30b
```

Non-interactive smoke test:

```bash
opencode run \
  --model ollama/qwen3-coder:30b \
  --agent plan \
  --file /tmp/artemis_T-0006_context.json \
  "Review this Artemis ticket context. Do not edit files. Return the next safe implementation step and the required validation commands."
```

For implementation tickets, use `--agent build`. For QA, use `--agent review`. For releases, use `--agent release`.

### 3. Optional OpenClaw wrapper

OpenClaw should be treated as an optional wrapper around the Artemis CLI, not as a source of truth. Start with an isolated dev profile:

```bash
openclaw --dev doctor
openclaw --dev gateway --port 19001
```

In another terminal, confirm the gateway status:

```bash
openclaw --dev status
```

Safe Artemis command surface for OpenClaw:

```bash
python -m pytest -q
pga validate-registries
pga validate-work-items
pga work-context --ticket T-0006 --output /tmp/artemis_T-0006_context.json
```

Do not expose these commands to OpenClaw until Artemis-native controls are stronger:

- `pga build-state-pack --publish`
- shared cache promotion
- source mapping changes
- convention changes
- trade submission
- broad shell or Git write commands

The recommended OpenClaw connection pattern is file-based:

```text
work/tickets/T-####.yaml -> pga work-context -> OpenClaw reads context -> proposed report or diff -> tests -> human review -> merge to main
```

### 4. Release loop for KB, skills, and agents

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
