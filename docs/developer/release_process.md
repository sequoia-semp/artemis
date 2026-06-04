# Release Process

Use the existing `pga release-check` or the Artemis alias:

```bash
artemis release check --ticket T-0018
```

Release candidates are generated as review artifacts only. Do not tag, publish, push, or promote
shared state automatically from a coding backend.
