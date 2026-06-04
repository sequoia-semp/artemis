# VCS Policy

Artemis uses local-first Git discipline. GitHub is a remote mirror and collaboration surface, not a paid project-management dependency.

No paid GitHub functionality is required for local development, tests, validation, work management, or release preparation.

## Branches

- `main`: stable, tested baseline.
- `intake/<name>`: temporary branch for merging or reviewing existing work.
- `ticket/T-####-slug`: normal implementation branch.
- `codex/T-####-slug`: normal Codex implementation branch.
- `spike/<topic>`: exploration; cannot merge directly unless converted into a ticket.

Prefer `codex/T-####-slug` for Codex-authored changes. The branch name should include the ticket ID.

## Local Environment

Use repo-local commands so validation does not depend on an activated shell:

```bash
make bootstrap
make validate
```

`make bootstrap` creates or refreshes `.venv` and installs `.[dev]` in editable mode. `make validate` runs tests, registry validation, work-item validation, and knowledge-base manifest validation. For an interactive shell, source:

```bash
. ./scripts/dev_env.sh
```

Use `make clean-local` to remove ignored Python caches and editable-install metadata. Use `make reset-venv` only when `.venv` needs to be rebuilt from scratch.

## Required Checks

Before merging:

```bash
make validate
pga vcs-ready --ticket T-####
```

If `pga` is not on PATH, use `.venv/bin/pga` or run the same check through:

```bash
make vcs-ready TICKET=T-####
```

## Standard Improvement Flow

```bash
git switch -c codex/T-####-slug
make validate
pga vcs-ready --ticket T-####
git status --short
git add <changed-files>
git commit -m "T-####: concise change summary"
git push -u origin codex/T-####-slug
```

Merge the ticket branch into `main` only after review and passing validation.

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
