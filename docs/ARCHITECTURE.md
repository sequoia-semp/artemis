# Current Architecture

Artemis is a model-agnostic Power + Gas analytics workbench. The current
architecture is controlled by a small root entrypoint layer, the machine-readable
`artemis.yaml` control plane, deterministic Python services, and descriptor-based
optional integrations.

## Root Entrypoint Layer

The root layer is intentionally small:

- `README.md`: product orientation, modes, commands, and docs pointer.
- `AGENTS.md`: behavioral contract for coding agents and LLMs.
- `llms.txt`: compact navigation index.
- `artemis.yaml`: machine-readable control plane.
- `pyproject.toml`: package metadata and CLI entrypoints.
- `Makefile`: validation and routine command gate.

Root files must not define market convention details, wrapper-specific
architecture, or planning records. Historical build packets, wrapper guides, and
planning bridge files live under archive or work-management paths.

## Control Plane

`artemis.yaml` is the current product control plane. It declares:

- product identity and package version
- authority files
- Analyst and Development modes
- role requirements
- optional provider profiles
- optional coding backend and orchestrator descriptors
- tool registry and permission paths
- knowledge-base, skill, view, and data-source manifest paths
- release validation commands

Domain convention details remain in `domain/`, locked convention docs,
registries, schemas, and tests. `artemis.yaml` wires the system together; it does
not replace deterministic authority.

## Analyst Mode

Analyst Mode is read-oriented. It can produce reports, summaries, candidate
notes, view models, and workspace outputs. It cannot modify repository files,
update canonical knowledge, approve mappings, alter locked conventions, publish
shared state, or submit trades.

Analyst workflows load `artemis.yaml`, resolve `mode=analyst`, apply tool
permissions, validate source descriptors and lineage, run deterministic tools,
and only then allow optional LLM explanation or synthesis.

## Development Mode

Development Mode is the controlled improvement path. It requires a ticket,
change-policy compliance, updated tests where behavior changes, and release
validation before promotion.

Development workflows load `artemis.yaml`, load the ticket and affected context,
attach tool policy and optional backend descriptors, produce a patch or handoff
bundle, run validation, and prepare release artifacts.

## Tool Bus

The tool bus is registry-backed. Tool definitions live in
`registries/tools.yaml`, and permissions live in `registries/tool_permissions.yaml`.
Tools are classified by risk and mode. Repository mutation remains gated by
Development Mode, ticket context, tests, and human review where required.

Runtime agent tools may retrieve, explain, compare, summarize, render views, and
draft scenarios. They may not silently mutate canonical state, source mappings,
market conventions, release approval, or execution workflows.

## Data-Source Descriptors

Data-source descriptors live in `registries/data_sources.yaml` and are validated
by schema. They describe source availability, credential environment names,
lineage expectations, and fixture policy.

Fixture, synthetic, and generated data are allowed for local tests and demos only
when explicitly marked. They cannot be promoted into authoritative shared state.

## Manifests

Current agent product surfaces are manifest-driven:

- `knowledge_base/MANIFEST.yaml`
- `skills/manifest.yaml`
- `views/manifest.yaml`
- `registries/data_sources.yaml`

These manifests are validated by `make validate` and the Artemis CLI. Prompt or
Markdown content is not authoritative unless it points to deterministic artifacts
or approved convention records.

## Optional Integration Descriptors

Providers, coding backends, and orchestrators are optional descriptors under
`integrations/`:

- `integrations/providers/`
- `integrations/coding_backends/`
- `integrations/orchestrators/`

These files describe how local tools, model runtimes, or external harnesses can
bind to Artemis roles. They are not authoritative for market conventions,
deterministic calculations, state/cache promotion, mappings, or release approval.

## Deterministic Analytics Core

The deterministic core lives in:

- `src/pga_workbench/`
- `registries/`
- `schemas/`
- `domain/`
- `docs/CONVENTIONS_LOCKED_v0.1.md`
- `tests/`

Calculations for normalization, quantities, period parsing, strip expansion,
spread decomposition, vol transformations, view rendering, release checks, and
validation must be implemented in tested code. LLM output may explain or propose;
it must not be the source of capital-sensitive calculations.

## Release Validation

`make validate` is the repository validation gate. It installs the package in the
local virtual environment, runs pytest, validates registries, validates work
items, validates the knowledge base, validates Artemis config, validates skill
and view manifests, validates data-source descriptors, and reports Artemis
capabilities.

Release readiness is checked through `artemis release check`. Release candidate
artifacts include package metadata, target version, ticket, validation command
statuses, manifest hashes where available, and a human-review requirement flag.
