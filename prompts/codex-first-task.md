Read `CODEX_IMPLEMENTATION_BRIEF.md` and the required files listed there. Then run `python -m pytest -q`.

Implement Slice 1 registry validation only:

- Load all YAML files under `registries/`.
- Validate them against the corresponding schemas where a schema exists.
- Reject duplicate IDs.
- Reject forbidden power basis orientations.
- Validate gas quantity convention remains `1 contract = 0.25/d = 2,500 MMBtu/day`.
- Add CLI command `pga validate-registries`.
- Add tests.
- Do not change market conventions.
- Do not start PnL, dashboards, fundamentals, or model routing.

Return files changed, tests added, and exact test output.
