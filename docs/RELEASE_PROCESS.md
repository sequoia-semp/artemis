# Release Process

Artemis versions code, schemas, registries, and conventions independently enough to preserve auditability.

## Package Versioning

The Python package follows semantic versioning:

- PATCH: docs, tests, or non-behavioral fixes.
- MINOR: additive parser, registry, schema, CLI, or service behavior.
- MAJOR: breaking convention, valuation, quantity, or schema semantics.

## Convention Versioning

Convention changes require a change request. The `.25/d` gas contract convention and approved power spread orientations must not change without a Class 6 change request and regression comparison.

## Schema And Registry Versioning

Schema changes need a compatibility note. Registry changes must preserve source lineage and avoid silently promoting unsupported products.

## Release Notes

Release notes should include:

- package version
- convention version or unchanged statement
- schema changes
- registry changes
- tests run
- known gaps

## Release Readiness

Run the deterministic release check before preparing a tag:

```bash
make release-check TICKET=T-####
```

For shells where `pga` is already available, the equivalent command is:

```bash
pga release-check --ticket T-####
```

This command reports package metadata, validation status, required release-note
fields, the current regression report summary, and whether the PJM MVP planning
bridge files are present.
