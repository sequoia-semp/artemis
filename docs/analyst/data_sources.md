# Data Sources

Data-source descriptors live in `registries/data_sources.yaml`. This slice defines file-drop,
vendor API, ISO API, and ICE exchange descriptor shapes only. It does not implement live
proprietary data calls.

Credential requirements are environment variable names, not secret values. Validate with:

```bash
artemis data-sources validate
```

Analysts can inspect compact source evidence from an accepted state root or a
workspace artifact bundle through the read-only source-audit path:

```bash
artemis analyst bundle source-audit --state-root /path/to/state_root --output /tmp/source_audit.json --allow-blockers
artemis analyst bundle source-audit --bundle /tmp/pjm_morning_bundle.json --output /tmp/source_audit.json --allow-blockers
```

The corresponding `analyst.audit_power_system_sources` skill may summarize,
explain, and identify blockers in the audit report. It may not approve source
publications, invent conventions, normalize candidate sources, or mutate cache
or state.
