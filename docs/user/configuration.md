# Artemis Configuration

`artemis.yaml` is the committed, non-secret project configuration. It defines the Artemis
mission, authority files, Analyst and Development modes, optional provider roles, tool
registries, manifests, data-source descriptors, and release validation commands.

Local machine settings belong in `local/artemis.local.yaml`, which is intentionally untracked.
Use `local/artemis.local.example.yaml` as the template. Credentials must be referenced by
environment variable name only.

Validate configuration with:

```bash
artemis config validate
```

Resolution order is:

1. `--config path.yaml`
2. `ARTEMIS_CONFIG`
3. `ARTEMIS_LOCAL_CONFIG` or `local/artemis.local.yaml`
4. `artemis.yaml`
