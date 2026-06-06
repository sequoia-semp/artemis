# Power System Operational Events

Operational events are source-published power-system records such as generation
outages and transmission constraints. They are separate from load, generation
mix, and price observations because their lifecycle, identity, topology
linkage, and impact semantics require stricter source-specific approval.

## Candidate Descriptor Layer

`power_system_operational_event_feeds.yaml` records candidate source feed
descriptors for operational events. A descriptor may identify the operator,
source feed name, event family, event class, timestamp policy, identifier
policy, topology linkage status, and source documents.

This layer is intentionally not a normalized event contract. Candidate
descriptors do not approve:

- outage lifecycle state;
- generation unit identity;
- constraint identity;
- topology graph linkage;
- Gantt chart semantics;
- congestion attribution;
- impact scoring; or
- shared-cache publication.

## Candidate Planning Report

Operational event planning is allowed only as non-mutating evidence. A candidate
plan may summarize source publications and feed descriptors, then list blockers
for approval. It must not fetch source rows, normalize outage or constraint
records, create topology links, publish state, or populate HotState views.

The current PJM candidate plan is expected to remain unapproved because outage
and constraint feeds still have pending timestamp, identifier, lifecycle,
normalization, and topology semantics. Those blockers are intentional guardrails
for future tickets.

The plan is exposed as a read-only CLI report through
`pjm-operational-event-plan` and `artemis data-sources
pjm-operational-event-plan`. The command validates the report before writing it.
It returns success for the expected candidate-only plan unless
`--require-approved` is supplied, which allows future promotion checks to fail
closed while preserving today's planning workflow.

Power-system artifact bundles may embed this report as compact planning
evidence. Embedding the plan preserves blockers for morning source review, but
does not approve source fetches, normalized operational-event contracts,
topology linkage, HotState views, or state-pack publication.

## PJM First Implementation

The first candidate descriptors are PJM Data Miner feeds for forecast generation
outages, day-ahead transmission constraints, and real-time transmission
constraints. They are linked from `power_system_source_catalog.yaml` so source
inventory and future implementation work can resolve feed IDs without promoting
the feeds into authoritative normalized artifacts.

Any future approval must add a normalized state contract, fixture coverage,
source field mapping, lineage, retention policy, publish safety tests, and
explicit topology/outage lifecycle documentation.
