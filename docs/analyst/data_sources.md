# Data Sources

Data-source descriptors live in `registries/data_sources.yaml`. This slice defines file-drop,
vendor API, ISO API, and ICE exchange descriptor shapes only. It does not implement live
proprietary data calls.

Credential requirements are environment variable names, not secret values. Validate with:

```bash
artemis data-sources validate
```
