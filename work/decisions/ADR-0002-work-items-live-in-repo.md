# ADR-0002: Work Items Live In Repo

## Decision

Epics, sprints, and tickets live in `work/` as versioned YAML files.

## Rationale

Repo-native work items give humans, Codex, and local LLMs the same auditable planning source without external service dependencies.

## Consequences

- Work item schemas live in `schemas/`.
- The `pga validate-work-items` command validates local work files.
- GitHub Issues are optional mirrors, not the source of truth.
