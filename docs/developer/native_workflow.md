# Native Workflow

GitHub is a plain remote. Do not use GitHub Actions, Issues, Projects, or PR
checks as workflow authority. Artemis owns validation, ticket lifecycle,
regression evidence, local-agent loops, and release readiness through native
repository commands.

Core commands:

```bash
make bootstrap
artemis validate --strict
artemis work validate
artemis work show T-0030
artemis dev context --ticket T-0030 --output /tmp/T-0030_context.json
artemis dev loop --ticket T-0040 --backend manual --dry-run
artemis release check --ticket T-0030
```

`make validate` is a compatibility wrapper around `artemis validate`. Use
`artemis validate report --input ... --markdown ...` to bridge machine-readable
validation evidence into curated regression reports.

Release readiness must fail when validation is skipped, stale, missing, tied to
the wrong ticket, non-strict, or disconnected from ticket lifecycle state. Coding
backends may propose patches, but deterministic Artemis checks decide readiness.

Runtime tools must pass executable mode policy before they run. Analyst mode is
limited to read-only and workspace-output actions. Development repo writes
require a ticket, release-candidate tools require passed native validation
context, and convention-changing actions require approved change-request context.
