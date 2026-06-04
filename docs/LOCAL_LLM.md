# Local LLM

Artemis supports optional local LLM workflows while keeping deterministic tests and services authoritative.

## Runtime

- Ollama is the initial optional local runtime.
- `local/llm_config.example.yaml` defines local context loading and safety settings.
- The local model is not authoritative for calculations, conventions, mappings, state packs, or cache publication.
- No paid GitHub or paid API dependency is required.

## Context

The agent runtime loads:

- startup guidance
- locked conventions
- assigned ticket YAML
- ticket affected files

The context loader does not call a model. It returns a deterministic context bundle for a local model or coding agent.

## Safety

Any update to canonical knowledge, domain rules, schemas, registries, or source code must go through reviewed work items, change requests when required, and tests.
