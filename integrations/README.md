# Integrations

Integrations are optional descriptors. They are not the Artemis architecture and
they are not authoritative for market conventions, deterministic calculations,
state/cache promotion, mappings, or release approval.

Primary descriptor directories:

- `integrations/providers/`: optional model/runtime provider descriptors.
- `integrations/coding_backends/`: optional coding or review backend descriptors.
- `integrations/orchestrators/`: optional outer-orchestration descriptors.

Compatibility examples:

- `integrations/opencode/`: legacy OpenCode example configuration.
- `integrations/ollama/`: legacy local-model examples.
- `integrations/openclaw/`: legacy read-only command manifest examples.
- `integrations/capability_registry.yaml`: compatibility capability registry used by `pga agent-capabilities`.

Descriptors referenced from `artemis.yaml` must exist and must not set
`authoritative: true`.
