# AGENTS.md

## Mission

This repository defines a model-agnostic Power + Gas Trading Analytics workbench. The system normalizes market indices, positions, marks, vol surfaces, periods, strips, spreads, and exposures into deterministic, auditable analytics artifacts.

## Core rules

1. Do not invent market convention.
2. Do not silently normalize unknown products.
3. Do not reverse quoted spread orientation.
4. Use deterministic code for calculations.
5. Treat LLM inference as candidate-only unless approved.
6. Preserve raw inputs, normalized outputs, source, timestamp, and lineage.
7. Fail closed on ambiguity.
8. Every material change requires tests.
9. Every convention change requires a change request.
10. Never remove or weaken tests to make behavior pass.
11. Gas contract sizing is `.25/d` per contract, not `1.0/d` per contract.

## Canonical source files

Read these before modifying behavior:

- `artemis.yaml`
- `README.md`
- `docs/README.md`
- `docs/CONVENTIONS_LOCKED_v0.1.md`
- `domain/source_policy.md`
- `domain/market_index_model.md`
- `domain/power_basis_conventions.md`
- `domain/gas_index_families.md`
- `domain/period_grammar.md`
- `domain/units_and_quantities.md`
- `development/CHANGE_POLICY.md`
- `registries/`
- `schemas/`
- `tests/`

`docs/BUILD_PACKET_v0.1.md`, wrapper setup docs, and root legacy implementation
briefs are design records or compatibility references. They do not override
`artemis.yaml`, locked conventions, registries, schemas, tests, or this file.

## Required development flow

For any behavioral change:

1. Create or update a change request in `development/change_requests/`.
2. Identify affected domain files, schemas, registries, skills, and tests.
3. Add or update regression tests.
4. Implement the smallest durable abstraction.
5. Run validation and regression tests.
6. Produce a regression report.
7. Do not promote the change unless tests pass and the change request is approved.

## Prohibited behavior

- No unsupported product additions.
- No inferred basis orientation.
- No unapproved power basis edges.
- No unapproved gas index-family assumptions except the approved GDD default.
- No power price component other than full LMP unless explicitly approved.
- No hidden prompt-only calculation logic.
- No production behavior change based only on model memory or confidence.

## Pure LLM mode

If you are a pure LLM with file-system access but no execution environment, you may inspect and modify files, draft tests, and propose code. You must mark any unexecuted claim as `UNEXECUTED`. Do not claim tests passed unless a tool actually ran them and produced logs.
