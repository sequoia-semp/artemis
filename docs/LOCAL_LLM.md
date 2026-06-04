# Local LLM

Artemis supports optional local LLM workflows while keeping deterministic tests and services authoritative.

## Runtime

- `local/artemis.local.example.yaml` defines optional local model/context profiles and local data-source credential env names.
- `local/llm_config.example.yaml` is a legacy compatibility example for older `pga work-context` callers.
- `deterministic_only` is the default profile and requires no model runtime.
- Ollama is an optional local runtime profile.
- External harnesses such as OpenCode, Codex, Claude Code, or another wrapper can own model invocation outside Artemis.
- The local model is not authoritative for calculations, conventions, mappings, state packs, or cache publication.
- No paid GitHub or paid API dependency is required.

## Context

The agent runtime loads:

- startup guidance
- locked conventions
- assigned ticket YAML
- ticket affected files

The context loader does not call a model. It returns a deterministic context bundle for a local model or coding agent.

The profile config is advisory. Deterministic commands such as `pga validate-registries`, `pga validate-work-items`, `artemis dev context`, and `pga work-context` must run without OpenCode, Ollama, OpenClaw, or any other wrapper.

## Safety

Any update to canonical knowledge, domain rules, schemas, registries, or source code must go through reviewed work items, change requests when required, and tests.

See also:

- `docs/OPENCODE_SETUP.md`
- `docs/WRAPPER_ABSTRACTION_POLICY.md`
- `docs/AGENT_MODES.md`
- `docs/AGENT_KB_SKILL_RELEASE_LOOP.md`
- `docs/AGENT_WRAPPER_EVALUATION.md`
