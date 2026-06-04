# OpenCode Integration (Compatibility Example)

OpenCode is an optional coding/review harness. It is not required for deterministic Artemis commands and is not authoritative for analytics behavior.

The active descriptor path is `integrations/coding_backends/opencode.yaml`.

Use the root `opencode.jsonc` as a conservative project config. Provider-specific examples live here so users can switch model/runtime choices without editing domain code.

Examples:

- `opencode.ollama.example.jsonc`: local Ollama provider.
- `opencode.external-model.example.jsonc`: placeholder for externally managed model/provider settings.

Root config should preserve these properties:

- edits are approval-gated
- broad shell commands are approval-gated
- `git push*` and `git tag*` are approval-gated
- deterministic validation commands are allowed
