# Artemis Build Agent

Edits allowed only with approval.

Rules:

- Do not modify locked conventions without change request.
- Do not modify domain, registries, schemas, or `src` without tests.
- Keep wrappers optional.
- Prefer the smallest durable abstraction.
- Run or request Artemis-native validation:

```bash
artemis validate --strict --ticket <ticket>
```

Prompt-only analytics are not authoritative; PnL, risk, Greeks, forecasts, state, mappings, and conventions must come from deterministic services, reviewed registries/schemas, and tests.
