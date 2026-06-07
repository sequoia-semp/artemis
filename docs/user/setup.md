# Artemis Setup

This guide covers the local path from a fresh clone to a validated Artemis
workspace, plus optional OpenCode/Ollama routing and local source configuration.

## Install

Use the repo-local bootstrap command so the package, console scripts, and test
dependencies live in `.venv`:

```bash
git clone https://github.com/sequoia-semp/artemis.git
cd artemis

make bootstrap
. ./scripts/dev_env.sh
artemis validate
```

The validation gate installs `pga-workbench` in editable mode, runs pytest, and
validates registries, work items, knowledge base entries, Artemis config, skills,
views, data-source descriptors, and capabilities.

## Core Commands

```bash
artemis validate --strict
artemis work validate
artemis config validate
artemis capabilities
artemis capabilities --check-network
artemis dev context --ticket T-0025 --output /tmp/T-0025_context.json
artemis dev loop --ticket T-0040 --backend manual --dry-run
artemis release check --ticket T-0030
```

`artemis` is the product/mode CLI. Lower-level deterministic commands remain
under `pga`, including normalization, risk, and state-pack commands.

GitHub is a plain remote only. Do not rely on GitHub Actions, Issues, Projects,
labels, or PR checks as workflow authority; native Artemis commands own
validation, work lifecycle, regression evidence, agent loops, and release
readiness.

## Local Configuration

Committed configuration lives in `artemis.yaml`. Local machine configuration is
untracked:

```bash
cp local/artemis.local.example.yaml local/artemis.local.yaml
cp local/.env.example local/.env
```

`local/artemis.local.yaml` controls non-secret runtime choices such as provider
profile and coding backend. `local/.env` holds local environment variables and
must not be committed.

Artemis loads `.env` and `local/.env` when present. To use a different file:

```bash
export ARTEMIS_ENV_FILE=/absolute/path/to/artemis.env
```

## Optional Ollama

Install and start Ollama, then pull the configured local model:

```bash
ollama pull qwen3-coder:30b
ollama serve
```

Keep `providers.default_profile: deterministic_only` for native Artemis
commands. The `local_ollama` profile may remain configured as an optional
external convenience profile, but it must not be the default deterministic
profile unless it declares an explicit determinism guarantee with pinned model
parameters.

Example optional profile configuration:

```yaml
providers:
  default_profile: deterministic_only
  profiles:
    local_ollama:
      kind: openai_compatible
      required: false
      descriptor: integrations/providers/openai_compatible.example.yaml
      base_url: http://localhost:11434/v1
      model: qwen3-coder:30b
      api_key_env: OLLAMA_API_KEY
```

Then verify:

```bash
artemis capabilities --check-network
```

Ollama is optional and non-authoritative. Deterministic calculations,
conventions, mappings, and release approval still come from code, registries,
schemas, tests, and human review.

## Optional OpenCode

OpenCode is an optional coding backend descriptor. Keep the root
`opencode.jsonc` as the permissions-only compatibility shim. Example configs
live under:

```text
integrations/coding_backends/opencode/
```

To advertise OpenCode as the preferred coding backend in development context,
set:

```yaml
backends:
  coding:
    default: opencode
```

Then generate context for the backend:

```bash
artemis dev context --ticket T-0025 --output /tmp/T-0025_context.json
artemis dev loop --ticket T-0040 --backend opencode --dry-run
```

## Environment Variables

Use `local/.env` or your shell for optional credentials and roots:

```bash
ARTEMIS_VENDOR_API_KEY=
ARTEMIS_ICE_API_KEY=
ARTEMIS_PJM_API_KEY=
ARTEMIS_PJM_API_BASE_URL=https://api.pjm.com/api/v1
ARTEMIS_PJM_ACCOUNT_CLASS=non_member
ARTEMIS_RUN_LIVE_PJM_TESTS=0
OLLAMA_API_KEY=ollama
ARTEMIS_OPENAI_COMPATIBLE_BASE_URL=http://localhost:11434/v1
ARTEMIS_OPENAI_COMPATIBLE_MODEL=qwen3-coder:30b
```

Credential values should never appear in committed config, fixtures, docs, logs,
or tests. Committed files should reference environment variable names only.

## File-Source Roots

For local marks, positions, trades, or internal source drops, configure roots in
`local/.env`:

```bash
ARTEMIS_MARKS_ROOT=/absolute/path/to/marks
ARTEMIS_POSITIONS_ROOT=/absolute/path/to/positions
ARTEMIS_TRADES_ROOT=/absolute/path/to/trades
ARTEMIS_INTERNAL_DB_ROOT=/absolute/path/to/internal_sources
```

These paths are reported by `artemis capabilities` as configured or missing.
They are local file-source bindings, not authoritative market conventions.

PJM Data Miner smoke usage:

```bash
artemis analyst fundamentals build-pjm-load \
  --live \
  --feed load_frcstd_7_day \
  --as-of 2026-06-06 \
  --start 2026-06-06 \
  --end 2026-06-06 \
  --area RTO_COMBINED \
  --row-count 24 \
  --max-pages 1 \
  --output /tmp/pjm_load_fundamentals.json
```

Publishable PJM load state pipeline:

```bash
artemis analyst bundle run-pjm-load-pipeline \
  --live \
  --as-of 2026-06-06T12:00:00Z \
  --start 2026-06-06 \
  --end 2026-06-06 \
  --row-count 24 \
  --max-pages 1 \
  --no-paginate \
  --output /tmp/pjm_load_bundle.json \
  --state-root /tmp/pjm_load_state \
  --state-id pjm-load-20260606 \
  --pipeline-output /tmp/pjm_load_pipeline.json \
  --publish
```

The load pipeline defaults to the approved `load_frcstd_7_day` feed. It fetches
live Data Miner rows, verifies feed metadata, embeds redacted readiness and raw
fetch evidence, stages a candidate state pack, and only publishes when the
source-publication gate passes.

Bounded PJM hourly LMP smoke usage:

```bash
artemis analyst prices build-pjm-lmp \
  --live \
  --location WH \
  --feed PJM_RT_HOURLY_LMP \
  --as-of 2026-06-01 \
  --start 2026-06-01 \
  --end 2026-06-01 \
  --row-count 24 \
  --max-pages 1 \
  --no-paginate \
  --output /tmp/pjm_lmp_prices.json
```

Daily shape rollup from hourly price artifacts:

```bash
artemis analyst prices rollup-shapes \
  --input /tmp/pjm_lmp_prices.json \
  --as-of 2026-06-01 \
  --output /tmp/pjm_lmp_daily_shapes.json
```

Live PJM requests default to the non-member Data Miner access policy: one page
per request plan, `rowCount <= 50000`, and no unbounded pagination. Set
`ARTEMIS_PJM_ACCOUNT_CLASS=member` only when the local operator has a PJM member
account. Live PJM tests are skipped unless `ARTEMIS_RUN_LIVE_PJM_TESTS=1` is set.

## Validation

Before handing work to another agent or backend:

```bash
artemis validate --strict
artemis validate report --input development/validation_reports/latest.json
artemis work validate
artemis release check --ticket T-0030
```

Use `--skip-tests` only for a dry-run inspection. Skipped validation does not
mean the repo is release-ready.
