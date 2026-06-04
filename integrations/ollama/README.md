# Ollama Integration (Compatibility Example)

Ollama is an optional local model runtime. Artemis deterministic commands, tests, registries, schemas, and context packaging must run without Ollama.

Use `model_profiles.yaml` as a legacy example and prefer `local/artemis.local.example.yaml`
for current local configuration. The context loader does not call Ollama or any
other model runtime.
