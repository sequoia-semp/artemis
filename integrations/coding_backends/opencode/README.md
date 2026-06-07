# OpenCode Backend Example

`integrations/coding_backends/opencode.yaml` is the active Artemis backend
descriptor. Files in this directory are optional OpenCode configuration examples
and are not authoritative for Artemis behavior.

The root `opencode.jsonc` is intentionally a small permissions-only shim for
tools that expect that filename at the repository root.

Use `opencode.ollama.example.jsonc` as a shape, not a model recommendation.
Replace `your-local-model` with any Ollama/OpenAI-compatible model available on
the machine, such as a local Kimi, DeepSeek, Qwen, or other model. Artemis
deterministic tools remain model-agnostic and authoritative; OpenCode/Ollama are
outer-loop convenience wrappers.
