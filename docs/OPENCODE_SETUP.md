# OpenCode Setup And Hardening

OpenCode is a development-agent harness for Artemis. It is not part of runtime analytics, cache publishing, state-pack acceptance, or trading decision authority.

## Current Local Status

Verified on 2026-06-04:

- `opencode` is installed locally.
- `ollama` is installed locally.
- Ollama was not running at `http://localhost:11434` during verification.

## Setup

1. Start Ollama:

   ```bash
   ollama serve
   ```

2. Pull a coding model if needed:

   ```bash
   ollama pull qwen3-coder:30b
   ```

3. From the repo root, validate deterministic state:

   ```bash
   python -m pytest -q
   pga validate-registries
   pga validate-work-items
   ```

4. Build a ticket context bundle:

   ```bash
   pga work-context --ticket T-0006 --output /tmp/artemis_T-0006_context.json
   ```

5. Start OpenCode with the local model:

   ```bash
   opencode . --model ollama/qwen3-coder:30b
   ```

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

## POC Acceptance Test

The first OpenCode proof of concept should use a low-risk ticket:

1. Load `T-0006` or another docs-only ticket.
2. Ask OpenCode to propose a small KB/skill documentation change.
3. Confirm it creates or updates a local work item.
4. Run:

   ```bash
   python -m pytest -q
   pga validate-registries
   pga validate-work-items
   ```

5. Confirm the diff does not touch domain conventions or authoritative analytics code unless a change request exists.
