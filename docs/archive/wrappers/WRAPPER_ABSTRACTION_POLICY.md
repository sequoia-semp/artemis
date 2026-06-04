# Wrapper Abstraction Policy

Artemis supports optional agent wrappers. Wrappers are replaceable.

## Source Of Truth

- Artemis repo files and deterministic `pga` commands are canonical.
- Wrappers do not define domain convention.
- Wrappers do not define product mappings.
- Wrappers do not publish state or promote cache artifacts without Artemis-native approval controls.

## Wrapper Roles

| Layer | Role | Required? | Authoritative? |
|---|---|---:|---:|
| `pga` CLI | deterministic command surface | yes | yes |
| `pga work-context` | context packaging | yes | yes |
| Ollama | local model runtime | no | no |
| OpenCode | coding/review harness | no | no |
| OpenClaw | outer orchestration/channel wrapper | no | no |

## Required Interaction Pattern

```text
work ticket
-> pga work-context
-> wrapper reads context
-> wrapper proposes patch/report
-> deterministic tests
-> human review
-> merge
```

## Forbidden By Default

- wrapper-native convention changes
- wrapper memory becoming canonical
- OpenClaw state-pack publish
- shared cache promotion
- source mapping changes
- registry/schema/domain changes without change request

## Availability Fallbacks

- If no wrapper is available, use `deterministic_only` mode.
- If Ollama is unavailable, use `external_harness` or `deterministic_only` mode.
- If OpenCode is unavailable, use Codex or another agent with `pga work-context` output.
- If OpenClaw is unavailable, no Artemis core functionality is lost.
