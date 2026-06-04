# Self-Development

Development Mode is ticket-gated and backend-neutral. Context is built from
`artemis.yaml`, optional local Artemis config overrides, the ticket, authority
files, tool policy, backend descriptors, release validation commands, and affected
file status.

A coding backend can help propose or review patches, but it is not authoritative
for market conventions, deterministic calculations, state publishing, or release
approval.

Useful commands:

```bash
artemis dev context --ticket T-0018 --output /tmp/T-0018_context.json
artemis dev plan --ticket T-0018
artemis release candidate --ticket T-0018 --output /tmp/RC-0.2.0-T-0018.yaml
artemis release check --ticket T-0018
```

`pga work-context` remains a compatibility alias for the same Artemis development
context shape.
