# Agent Wrapper Evaluation

Artemis can support multiple agent wrappers, but wrappers must remain orchestration layers around deterministic services.

## Current Primary Harness: OpenCode

OpenCode is the first development harness because this repo already includes `opencode.jsonc`, local agent roles, and command permissions. It is appropriate for code editing, review loops, local context loading, and ticket execution.

## Candidate: OpenClaw

OpenClaw describes itself as a personal AI assistant with a local-first gateway, multi-channel inbox, multi-agent routing, tools, skills, browser/canvas automation, and daemonized gateway setup. Its own README highlights a security model where default tools run on the host for the main session and sandboxing should be configured for non-main sessions.

Recommended Artemis posture:

- Do not integrate OpenClaw directly into authoritative analytics.
- Treat OpenClaw as an optional outer orchestration/channel layer.
- Only expose read-only Artemis commands first: `pga work-context`, `pga validate-*`, and report-generation commands.
- Require sandboxing before write/edit/shell workflows.
- Never expose shared cache publishing, state-pack promotion, or secrets by default.

Reference: https://github.com/openclaw/openclaw

## Candidate: Hermes Agent

Hermes Agent describes itself as a self-improving agent with CLI, messaging gateway, skills, memory, MCP integration, scheduled automations, and local/container/SSH/cloud terminal backends. Its documentation also describes a layered trust model and sandboxing concerns for terminal backends and whole-process wrapping.

Recommended Artemis posture:

- Treat Hermes as an optional long-running assistant wrapper, not as the source of analytics truth.
- Do not import Hermes memory into canonical Artemis KB without review.
- Consider Hermes only after OpenCode and local context loading are stable.
- Prefer a file-based bridge: Hermes reads ticket context bundles and writes proposed change requests or reports.
- Keep mutating Git, cache, and state actions behind explicit approval.

References:

- https://github.com/NousResearch/hermes-agent
- https://github.com/NousResearch/hermes-agent/security

## Wrapper Adapter Shape

Wrappers should integrate through files and CLI commands, not direct mutation:

```text
work ticket -> pga work-context -> wrapper reads context -> proposed diff/report -> tests -> review -> merge
```

Initial allowed command surface:

- `pga work-context`
- `pga validate-work-items`
- `pga validate-registries`
- `python -m pytest -q`
- read-only report commands

Deferred command surface:

- state-pack publish
- cache promotion
- source mapping changes
- trade submission
- convention changes

These deferred actions require explicit Artemis-native controls before any wrapper can use them.
