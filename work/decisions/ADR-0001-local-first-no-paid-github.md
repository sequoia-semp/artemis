# ADR-0001: Local First, No Paid GitHub Dependency

## Decision

Artemis must remain locally runnable and governable without paid GitHub features.

## Rationale

Trading analytics, tests, validation, work item loading, and local LLM context assembly should work on a MacBook Pro with local Git and Python.

## Consequences

- Local YAML work items are canonical.
- GitHub Issues and pull requests may mirror local state.
- GitHub Actions may be useful but are not authoritative.
- Paid GitHub Projects or Copilot features are not required.
