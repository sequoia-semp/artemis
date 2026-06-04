# Codex Workflow

Future Codex agents should follow this flow:

1. Read `AGENTS.md`.
2. Read `llms.txt`.
3. Read `docs/CONVENTIONS_LOCKED_v0.1.md`.
4. Read `development/CHANGE_POLICY.md`.
5. Read assigned `work/tickets/T-####.yaml`.
6. Inspect files listed under `affected_files`.
7. Create or update a change request if needed.
8. Add or update tests.
9. Make the minimal durable patch.
10. Use `make bootstrap` if `.venv` or `pga` are not available in the current shell.
11. Run `make validate`.
12. Run `pga vcs-ready --ticket T-####` or `make vcs-ready TICKET=T-####` before commit/merge prep.
13. Write a regression report when behavior changes.
14. Commit on a `codex/T-####-slug` branch and push for review when the user asks for remote publication.
15. Stop for review.

Do not change locked market conventions from prompt memory or model confidence.

## Local Command Standard

Codex agents should prefer repo-local wrappers:

```bash
make bootstrap
make validate
make work-context TICKET=T-####
make vcs-ready TICKET=T-####
```

This avoids relying on globally installed `python`, `pytest`, or `pga`.
