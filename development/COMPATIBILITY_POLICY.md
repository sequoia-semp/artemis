# Compatibility Policy

Behavior-changing updates must preserve interpretability of old artifacts or provide a migration note.

Major version bump triggers:

- breaking schema change
- changed spread orientation
- changed gas quantity convention
- changed power price component
- changed PnL semantics

Minor version bump triggers:

- new supported product/location/index
- optional schema extension
- new skill/workflow

Patch version bump triggers:

- documentation clarification
- bug fix preserving semantics
- test additions
