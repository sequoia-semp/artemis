# Agent KB And Skill Release Loop

Artemis treats knowledge, skills, prompts, and agent configuration as versioned release artifacts.

## Artifact Classes

- `knowledge_base/`: approved market, source, workflow, and operating knowledge.
- `skills/`: reusable analytical procedures for humans and agents.
- `.agents/skills/`: agent-runtime skill mirrors when needed.
- `.opencode/agents/`: OpenCode subagent roles and permissions.
- `prompts/`: task entry prompts and handoff prompts.
- `evals/`: invariant and regression checks for semantic behavior.

## Incremental Flow

1. Create or select a ticket in `work/tickets/`.
2. Generate context with `pga work-context --ticket T-####`.
3. Decide whether a change request is required.
4. Update KB, skills, prompts, code, or tests on a ticket branch.
5. Run:

   ```bash
   python -m pytest -q
   pga validate-registries
   pga validate-work-items
   ```

6. Request QA/reconciliation review.
7. Merge to `main`.
8. Tag or include in the next release note.

## Promotion Rules

- KB text is advisory unless backed by locked conventions, source docs, registries, schemas, or deterministic services.
- Skills that describe calculations must point to deterministic services or tests.
- Prompt-only analytics are not authoritative.
- A release may include KB/skill updates without package-version changes only if no behavior changes.
- Any convention, valuation, parser, registry, or schema change follows `development/CHANGE_POLICY.md`.

## Live/Main Release Boundary

`main` is the live, shared baseline. Agents can work on ticket branches, but only merged and validated artifacts on `main` are considered released for the workbench.
