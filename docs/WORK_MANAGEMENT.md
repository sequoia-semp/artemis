# Work Management

Local YAML work items are canonical. GitHub Issues may mirror them but are not required for local operation.

## Work Item Types

- Epic: a multi-sprint outcome.
- Sprint: a bounded set of tickets grouped for delivery.
- Ticket: an implementation or analysis unit that can be tested and reviewed.
- Decision/ADR: a durable architectural or workflow decision.
- Change request: required control record for material behavior or convention changes.

## Rules

- Work items live under `work/`.
- Change requests live under `development/change_requests/`.
- Tickets should identify affected files, required tests, and whether a change request is needed.
- GitHub labels, issues, and milestones are optional mirrors.
- A ticket may not override `AGENTS.md`, locked conventions, or change policy.
