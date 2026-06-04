# Agent Modes

Artemis agent modes describe optional wrapper use. They do not change domain authority, convention ownership, or deterministic validation requirements.

## Mode 0: `deterministic_only`

No model runtime or wrapper. Run `pga` and tests locally.

Safe commands:

```bash
python -m pytest -q
pga validate-registries
pga validate-work-items
```

## Mode 1: `context_bundle_manual`

Generate `pga work-context` and provide the JSON bundle to any LLM or coding agent.

Safe commands:

```bash
pga work-context --ticket T-0009 --output /tmp/artemis_T-0009_context.json
```

## Mode 2: `opencode_external_model`

Use OpenCode with a user-selected model/provider. Artemis does not care which model is selected.

Safe commands:

```bash
opencode . --agent plan
opencode . --agent review
```

## Mode 3: `opencode_ollama`

Use OpenCode with Ollama as a convenient local model runtime. This mode is optional and not required by package tests.

Safe commands:

```bash
ollama serve
opencode . --model ollama/qwen3-coder:30b
```

## Mode 4: `openclaw_readonly`

OpenClaw may trigger read-only `pga` commands through the read-only manifest in `integrations/openclaw/`.

Safe commands:

```bash
pga work-context --ticket T-0009 --output /tmp/artemis_T-0009_context.json
pga validate-registries
pga validate-work-items
```

## Mode 5: `future_openclaw_sandboxed_dev`

Future mode only. Requires sandboxing, explicit allowlist, tests, auditability, and human approval before any write command is exposed.
