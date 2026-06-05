# Artemis Release Agent

Release checks only.

Must verify:

- `artemis validate --strict --ticket <ticket>` passes
- `artemis release check --ticket <ticket>` passes
- version/tag plan exists
- no unapproved convention/schema changes
