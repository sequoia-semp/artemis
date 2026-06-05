# Power + Gas Trading Agent Workbench Scope

This record describes the current business scope around the Artemis architecture.
It does not override `artemis.yaml`, `AGENTS.md`, locked convention records,
registries, schemas, or tests.

## Current Geographic Scope

The workbench is PJM-first and designed to expand across the Eastern
Interconnection. Current architecture hooks support eastern power and gas
analytics without making unsupported source or convention assumptions.

Initial source-backed views focus on PJM and adjacent eastern gas fundamentals.
Broader Eastern Interconnection coverage is expected to enter through approved
data-source descriptors, registries, fixtures, and tests before it becomes
authoritative.

## ICE Scope

ICE products are represented through source and product descriptors. Artemis can
validate that declared ICE settlement and forward-curve contracts are present in
the configured registries, but it does not make live ICE calls or treat
ICE-like fixture data as authoritative without committed source documentation,
fixtures, lineage rules, and tests.

## +/-14-Day Analyst Scope

The near-term analyst horizon is a +/-14-day workflow:

- prior-day retrospective against forecast and observed artifacts
- current-day outlook from validated source-backed inputs
- forward-looking 14-day fundamentals and price context
- backhistory for key variables where retained source artifacts exist
- view outputs from deterministic view models before optional narrative

This scope is implemented through data-source descriptors, view templates, skill
manifests, and deterministic services. Analyst Mode may summarize and explain
the resulting artifacts, but it may not promote new source assumptions or modify
canonical configuration.

## State And Cache Safety

Morning state packs are built in candidate directories, validated, then promoted
by atomic pointer swap. Accepted state packs are immutable. Shared-readonly mode
cannot publish, and synthetic state packs cannot be promoted into authoritative
shared cache.

## Runtime Boundaries

Optional model runtimes, coding tools, and orchestrators are descriptors under
`integrations/`. They are not the product architecture and are not sources of
market convention, analytics calculation, source mapping, state promotion, or
release approval.
