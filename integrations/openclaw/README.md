# OpenClaw Integration

OpenClaw is optional outer orchestration only. It must not become authoritative for analytics, state-pack publishing, cache promotion, source mapping, registry updates, or convention changes.

Start with `artemis_tools.readonly.yaml` as a manifest of read-only commands. Confirm your local OpenClaw installation, CLI syntax, and sandbox mode before adapting the manifest into executable wrapper configuration.

The allowed initial posture is read-only:

- `pga work-context`
- `pga validate-registries`
- `pga validate-work-items`
- `python -m pytest -q`
