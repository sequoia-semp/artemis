# Artemis Build Agent

Edits allowed only with approval.

Rules:

- Do not modify locked conventions without change request.
- Do not modify domain, registries, schemas, or `src` without tests.
- Keep wrappers optional.
- Prefer the smallest durable abstraction.
- Run or request:

```bash
python -m pytest -q
pga validate-registries
pga validate-work-items
```
