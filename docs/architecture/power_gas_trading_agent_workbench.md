# Power + Gas Trading Agent Workbench

The workbench is deterministic-first. PnL, risk, Greeks, state packs, cache promotion, and normalized artifacts are authoritative only when produced by tested Python services. Agent output is advisory unless it cites durable artifacts from those services.

## Runtime Boundaries

- OpenCode configuration is for development-agent workflows only.
- Local Ollama integration belongs behind `adapters/local_model` and must not be required for deterministic commands.
- Agent tools may retrieve, explain, compare, summarize, and draft scenarios. Mutating rules, mappings, state packs, cache, and shared artifacts require reviewed change requests and tests.

## State And Cache Safety

Morning state packs are built in candidate directories, validated, then promoted by atomic `current.json` pointer swap. Accepted state packs are immutable. Shared-readonly mode cannot publish, and synthetic state packs cannot be promoted into authoritative shared cache.

## Initial Production Scope

The first production scope is PJM plus eastern gas. Positions and marks start as CSV/table inputs. PJM official fundamentals and forecasts are source-first, but live API behavior is canonical only after docs or Swagger are committed into the repository and covered by fixtures.
