# Artemis Setup

This guide covers the local path from a fresh clone to a validated Artemis
workspace, plus optional OpenCode/Ollama routing and local source configuration.

## Install

Use the repo-local bootstrap command so the package, console scripts, and test
dependencies live in `.venv`:

```bash
make bootstrap
. ./scripts/dev_env.sh
make validate
```

The validation gate installs `pga-workbench` in editable mode, runs pytest, and
validates registries, work items, knowledge base entries, Artemis config, skills,
views, data-source descriptors, and capabilities.

## Core Commands

```bash
artemis config validate
artemis capabilities
artemis capabilities --check-network
artemis dev context --ticket T-0025 --output /tmp/T-0025_context.json
```

`artemis` is the product/mode CLI. Lower-level deterministic commands remain
under `pga`, including normalization, risk, and state-pack commands.

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

In `local/artemis.local.yaml`, set:

```yaml
providers:
  default_profile: local_ollama
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
```

## Environment Variables

Use `local/.env` or your shell for optional credentials and roots:

```bash
ARTEMIS_VENDOR_API_KEY=
ARTEMIS_ICE_API_KEY=
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

## Validation

Before handing work to another agent or backend:

```bash
make validate
artemis release check --ticket T-0025
```

Use `--skip-tests` only for a dry-run inspection. Skipped validation does not
mean the repo is release-ready.
