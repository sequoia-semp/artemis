# Legacy Agent Start Note

This file is retained as a compatibility pointer for older tickets.

Current entrypoint:

1. Read `AGENTS.md`.
2. Inspect `artemis.yaml`.
3. Use `docs/README.md` for docs navigation.
4. Run:

```bash
make validate
artemis capabilities
```

Do not treat older build-packet or wrapper notes as the primary architecture.
Locked conventions, registries, schemas, tests, and `artemis.yaml` are the
current control plane.
