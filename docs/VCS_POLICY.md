# VCS Policy

Artemis uses local-first Git discipline. GitHub is a remote mirror and collaboration surface, not a paid project-management dependency.

No paid GitHub functionality is required for local development, tests, validation, work management, or release preparation.

## Branches

- `main`: stable, tested baseline.
- `intake/<name>`: temporary branch for merging or reviewing existing work.
- `ticket/T-####-slug`: normal implementation branch.
- `spike/<topic>`: exploration; cannot merge directly unless converted into a ticket.

## Required Checks

Before merging:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
pga validate-registries
```

## Change Rules

- Behavior change requires tests.
- Convention change requires a change request.
- Class 3+ changes require a change request.
- Class 5+ changes require regression comparison.
- Schema change requires a schema version note or explicit compatibility statement.
- Do not directly rewrite the `.25/d` gas convention.

## Tags

- `baseline/pre-governance`: baseline before the repo-native governance scaffold.
- `v0.1.0`, `v0.2.0`, and later semantic release tags.
