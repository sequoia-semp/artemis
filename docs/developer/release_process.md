# Release Process

Use the existing `pga release-check` or the Artemis alias:

```bash
artemis release check --ticket T-0018
```

Release candidates are generated as review artifacts only. Do not tag, publish, push, or promote
shared state automatically from a coding backend.

`artemis release check` reads `release.validation_commands` from `artemis.yaml`.
That command list is the release validation source of truth; wrapper prompts may
request validation but must not define independent release command inventories.
Release candidates include package version, command statuses, and hashes for the
key config/manifest files. Human approval, merge, tag, and publication remain
separate actions.

Use `--skip-tests` only for dry-run inspection. Skipped validations are recorded
as skipped and do not make a release candidate ready.

Native validation reports used for release readiness must be strict, passed, not
skipped, ticket-matched, and fresh for the ticket affected-file snapshot.
Reports must include passed context-audit evidence so wrapper and prompt drift
cannot pass release readiness silently.
Approved change requests must include affected files, required tests, and a
rollback plan. Locked convention file changes require change-request gating even
when the ticket omits the flag.
