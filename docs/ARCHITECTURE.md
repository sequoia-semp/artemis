# Architecture

## Layering

```text
Raw inputs
  -> registry-backed normalization
  -> canonical surfaces/positions/exposures
  -> deterministic analytics
  -> exception reports
  -> agent interpretation and narrative
  -> controlled improvement loop
```

## Canonical layers

1. Domain conventions live in `domain/`.
2. Machine-readable registries live in `registries/`.
3. JSON schemas live in `schemas/`.
4. Deterministic code lives in `src/pga_workbench/` and `analytics/`.
5. Agent-facing skills live in `skills/`.
6. Agent role definitions live in `agents/`.
7. Tests and evals live in `tests/` and `evals/`.
8. Change control lives in `development/`.

## Model agnosticism

Canonical instructions are plain Markdown, YAML, and JSON Schema. Model/provider-specific code belongs only in `adapters/`.

## Deterministic-first rule

LLMs may explain and propose. They must not calculate capital-sensitive values in free text. Value, exposure, PnL, period expansion, strip weighting, spread decomposition, and vol transformations must be deterministic and tested.
