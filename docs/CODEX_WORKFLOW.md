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
10. Run `python -m pytest -q` and `pga validate-registries`.
11. Run `pga validate-work-items` when work files, release docs, or agent configuration change.
12. Write a regression report when behavior changes.
13. Stop for review.

Do not change locked market conventions from prompt memory or model confidence.
