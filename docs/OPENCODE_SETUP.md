# OpenCode Setup And Hardening

OpenCode is an optional development-agent harness for Artemis. It is not part of runtime analytics, cache publishing, state-pack acceptance, or trading decision authority.

## Current Local Status

Verified on 2026-06-04:

- `opencode` is installed locally.
- `ollama` is installed locally.
- Ollama was not running at `http://localhost:11434` during verification.

## Setup

1. Validate deterministic state:

   ```bash
   python -m pytest -q
   pga validate-registries
   pga validate-work-items
   ```

2. Build a ticket context bundle:

   ```bash
   pga work-context --ticket T-0009 --output /tmp/artemis_T-0009_context.json
   ```

3. Choose a model/provider.

   The root `opencode.jsonc` has a local Ollama convenience default, but Artemis core does not require Ollama. Override the model/provider at runtime or use an alternate config under `integrations/opencode/`.

4. Optional local Ollama path:

   ```bash
   ollama serve
   ollama pull qwen3-coder:30b
   opencode . --model ollama/qwen3-coder:30b
   ```

5. External provider path:

   ```bash
   opencode . --agent plan
   ```

OpenCode must consume Artemis context and propose patches/reports. It does not enforce Artemis domain policy by itself.

## Config Examples

Provider-specific examples are under:

- `integrations/opencode/opencode.ollama.example.jsonc`
- `integrations/opencode/opencode.external-model.example.jsonc`

## Agent Modes

- `plan`: no edits; use for ticket planning and context review.
- `build`: edits require approval; use for implementation tickets.
- `review`: no edits; use for QA and reconciliation review.
- `release`: release actions require approval; use for tags and release checks.

## Hardening Rules

- Keep `*` bash behavior at `ask`.
- Allow only deterministic read/check commands by default.
- Keep `git push*`, `git tag*`, package installs, and broad shell commands behind approval.
- Never put secrets, tokens, or API keys in `opencode.jsonc`.
- Use `pga work-context` rather than asking OpenCode to scrape the repo ad hoc.
- For any analytics behavior change, require tests and change requests when `development/CHANGE_POLICY.md` says so.
- Do not rely on OpenCode to enforce Artemis domain policy.

## POC Acceptance Test

The first OpenCode proof of concept should use a low-risk ticket:

1. Load `T-0009` or another low-risk ticket.
2. Ask OpenCode to propose a small KB/skill documentation change.
3. Confirm it creates or updates a local work item.
4. Run:

   ```bash
   python -m pytest -q
   pga validate-registries
   pga validate-work-items
   ```

5. Confirm the diff does not touch domain conventions or authoritative analytics code unless a change request exists.
