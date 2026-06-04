# Ollama Integration

Ollama is an optional local model runtime. Artemis deterministic commands, tests, registries, schemas, and context packaging must run without Ollama.

Use `model_profiles.yaml` and `local/llm_config.example.yaml` as examples. The context loader does not call Ollama or any other model runtime.
