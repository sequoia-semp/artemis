# Self-Development

Development Mode is ticket-gated and backend-neutral. A coding backend can help propose or
review patches, but it is not authoritative for market conventions, deterministic calculations,
state publishing, or release approval.

Useful commands:

```bash
artemis dev context --ticket T-0018 --output /tmp/T-0018_context.json
artemis dev plan --ticket T-0018
artemis release candidate --ticket T-0018 --output /tmp/RC-0.2.0-T-0018.yaml
artemis release check --ticket T-0018
```
