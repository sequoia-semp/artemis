# Codex / Coding-Agent Implementation Brief v0.2

## Purpose

Use `power-gas-analytics-agent-packet-v0_1` as the seed for a real local repository. The first objective is not a full trading dashboard or autonomous agent. The first objective is to finish the deterministic semantic base so every later agent/LLM can safely operate on canonical market-index, period, spread, ATC, gas-index, price-surface, vol-surface, and position objects.

## Required first read order

A coding agent must read these files before editing:

1. `AGENTS.md`
2. `NEXT_AGENT_START_HERE.md`
3. `docs/BUILD_PACKET_v0.1.md`
4. `docs/CONVENTIONS_LOCKED_v0.1.md`
5. `development/CHANGE_POLICY.md`
6. `development/IMPROVEMENT_LOOP.md`
7. `development/change_requests/CR-0001-convention-firewall.yaml`
8. `development/change_requests/CR-0002-gas-contract-sizing-point25d.yaml`

Then run:

```bash
python -m pytest -q
```

Do not change behavior until the baseline tests pass.

## Non-negotiable implementation constraints

- Do not invent market conventions.
- Do not reverse quoted spread orientation.
- Do not silently normalize unknown products.
- Treat LLM inference as candidate-only.
- Use deterministic code for calculations.
- Every behavioral change requires a change request and regression tests.
- Keep canonical files model-agnostic. Provider-specific files belong in `adapters/`, `.opencode/`, or similar adapter folders.

## First implementation milestone

Implement Slice 1: deterministic normalization and validation.

Required deliverables:

1. Registry loader and validator.
2. JSON Schema validation for registries and artifacts.
3. Raw mark schema + normalizer.
4. Raw position schema + normalizer.
5. PriceSurfacePoint artifact writer.
6. NormalizedPosition artifact writer.
7. ExceptionReport artifact writer.
8. RunManifest artifact writer.
9. CLI entry points:
   - `pga validate-registries`
   - `pga parse-period <label>`
   - `pga normalize-prices --input data/raw/marks.csv --output data/artifacts/price_surface.json`
   - `pga normalize-positions --positions data/raw/positions.csv --marks data/artifacts/price_surface.json --output data/artifacts/normalized_positions.json`
10. Regression tests for every new behavior.

## Suggested branch sequence

```bash
git checkout -b slice-1-registry-validation
# implement registry validation and tests

git checkout -b slice-1-artifact-normalization
# implement raw mark/position normalization and artifacts

git checkout -b slice-1-agent-adapters
# add OpenCode/Ollama/LiteLLM optional adapters without changing core logic
```

## Required test policy

Before each commit:

```bash
python -m pytest -q
```

For behavior changes, add or update one of:

- `tests/test_*.py`
- `evals/regression/*.yaml`
- `evals/invariants/*.yaml`

Never remove or weaken a test to make a change pass.

## Output discipline

Each implementation PR/diff should include:

- Files changed.
- Behavior changed or not changed.
- Change request ID, if required.
- Tests added.
- Test results.
- Any remaining exceptions or unresolved assumptions.

## Model-router principle

The core package must run without any LLM. LLM routing is optional and should be isolated behind adapters:

- `.opencode/` for OpenCode local agent usage.
- `adapters/llm_gateway/` for LiteLLM or similar provider gateway.
- `adapters/local_model/` for Ollama-specific examples.
- `adapters/mcp/` for future tool exposure.

