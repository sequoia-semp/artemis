# Local Agent Loop

The native loop wraps ticket context generation, optional backend handoff,
validation, and release checking without relying on GitHub-native workflow
features.

Manual dry-run:

```bash
artemis dev loop --ticket T-0040 --backend manual --dry-run
```

Manual non-dry-run:

```bash
artemis dev loop --ticket T-0040 --backend manual
```

The non-dry-run path invokes `artemis validate` semantics through the native
validation runner, writes a validation report, then runs the native release
check.

OpenCode is optional. Artemis validates that the backend descriptor is
non-authoritative and refuses automatic backend execution unless explicitly
requested by a future implementation. The loop never runs `git push`, `git tag`,
or state-pack publishing commands.
