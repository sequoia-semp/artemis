# Power System State Candidates

This document describes candidate state-pack staging from power-system artifact
bundles. It does not change accepted-state publish rules.

## Purpose

Power-system bundles are workspace artifacts. A candidate state pack is the next
validation boundary before any accepted-state publish. Staging a candidate from
a bundle allows the existing state-pack validator to check delivery windows,
artifact composition metadata, artifact-product publish eligibility, and state
manifest consistency.

## Boundary

Candidate staging:

- validates the power-system bundle;
- writes `state_pack.json` under `candidates/<state_id>`;
- records the bundle as the manifest input;
- returns a staging report.

Candidate staging does not:

- write or update `current.json`;
- move the candidate into `accepted`;
- bypass synthetic-data, shared-readonly, or artifact-product publish gates;
- fetch live source observations.

Accepted-state publish remains the existing explicit state publisher operation.
At publish time, power-system bundles with source publication evidence are also
checked against publication status. Production-like bundles can publish only
when every evidenced source publication is `approved_core` and carries
`approved_source_surface` authoritative use. Candidate or non-approved source
publication evidence, such as PJM load actual candidate metadata, blocks
accepted-state promotion. Fixture, test, development, and local bundle
environments remain explicitly local-only and may publish in local validation
state roots.

## Candidate-Only Pipeline

`run-pjm-morning-pipeline` and
`artemis analyst bundle run-pjm-morning-pipeline` compose the current PJM
morning bundle and stage it as a candidate state pack in one operation. The
pipeline writes a bundle artifact and a pipeline report, then uses candidate
staging. It does not publish accepted state.

When the input bundle carries source readiness evidence, the pipeline report
includes a compact readiness summary with the ready flag, blocker count,
source-row fetch status, and row counts. The report summary is copied from
already-redacted bundle metadata and does not include raw source rows,
credentials, or request headers.
