# Integrations

Integrations are optional descriptors. They are not the Artemis architecture and
they are not authoritative for market conventions, deterministic calculations,
state/cache promotion, mappings, or release approval.

Primary descriptor directories:

- `integrations/providers/`: optional model/runtime provider descriptors.
- `integrations/coding_backends/`: optional coding or review backend descriptors.
- `integrations/orchestrators/`: optional outer-orchestration descriptors.

Compatibility examples:

- `integrations/coding_backends/opencode/`: optional OpenCode config examples.
- `integrations/providers/ollama_model_profiles.legacy.yaml`: legacy local-model profile examples.
- `integrations/orchestrators/openclaw_tools.readonly.yaml`: legacy read-only command manifest example.
- `integrations/capability_registry.yaml`: compatibility capability registry used by `pga agent-capabilities`.

Descriptors referenced from `artemis.yaml` must exist and must not set
`authoritative: true`.
