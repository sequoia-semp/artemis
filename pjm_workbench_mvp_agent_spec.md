# PJM Workbench MVP Agent Spec

This root-level file is the PJM-specific planning bridge referenced by `AGENTS.md`.
It does not replace the broader Artemis control plane. The canonical general
architecture starts at `artemis.yaml`, `AGENTS.md`, `README.md`, and
`docs/README.md`. Historical build-packet docs remain design records.

## MVP Mission

Build a PJM-first Textual workbench backed by deterministic Python services,
immutable accepted Morning State Packs, a read-through hot state/cache layer,
forecast-retention policy, topology hooks, and read-only agent tooling.

## Required Workflows

1. Retrospective on prior day versus morning forecast.
2. Morning PJM Summary of Changes.
3. Plus/minus 14 day dashboard with full backhistory for key variables.
4. Transmission outages/changes Gantt chart plus map-ready topology hooks.
5. Forward price heatmap with 1d, 5d, 10d, and 30d history.

## Architecture Bridge

- Domain conventions: `domain/`
- Machine-readable registries: `registries/`
- JSON schemas: `schemas/`
- Deterministic package CLI and services: `src/pga_workbench/`
- State/cache policy: `configs/cache_policy.yaml`
- Forecast retention policy: `configs/forecast_retention_policy.yaml`
- Work management: `work/`

## Current Status

The repository is still in scaffold/MVP-core phase. Registry-driven normalization,
state-pack hardening, forecast revision products, topology services, Textual screens,
and dashboard workflows should be implemented through local YAML tickets and tested
with deterministic services before agent narrative is treated as usable output.
