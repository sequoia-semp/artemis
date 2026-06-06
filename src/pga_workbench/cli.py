from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import yaml

from .agent.runtime import collect_artemis_capabilities, dump_config_yaml, load_artemis_config, validate_artemis_config
from .analyst.view_engine import build_view, merge_hot_state_artifacts, validate_view_manifest
from .core.time import utc_now_iso
from .data.contracts import DataRequest
from .data.connectors.pjm_dataminer import PjmDataMinerConnector
from .data.sources import credential_env_names, validate_data_sources
from .exceptions import WorkbenchException
from .dev.coding_backend import validate_coding_backends
from .dev.patch_context import collect_development_context
from .dev.release import build_release_candidate
from .models import RunManifest
from .periods import parse_period
from .registry import load_yaml_unique, validate_registries
from .serialization import read_json, to_plain, write_json
from .services.greeks import read_option_rows, run_black76_greeks
from .services.heatmap import build_forward_price_heatmap, read_price_surface_points, validate_forward_price_heatmap
from .services.fundamentals import build_pjm_load_artifacts, load_pjm_fundamental_feeds, normalize_pjm_fundamental_records, validate_fundamental_state
from .services.artifact_composition import compose_artifact_payloads
from .services.generation_mix import (
    build_pjm_generation_mix_artifacts,
    load_power_generation_mix_feeds,
    normalize_pjm_generation_mix_records,
    validate_generation_mix_state,
)
from .services.normalization import normalize_marks, normalize_positions, read_csv_rows
from .services.power_prices import (
    build_pjm_power_price_artifacts,
    load_power_system_price_feeds,
    normalize_pjm_lmp_records,
    normalize_pjm_pnode_records,
    validate_power_price_state,
)
from .services.power_price_shapes import build_power_price_shape_artifacts, validate_power_price_shape_state
from .services.power_system_ingestion import build_power_system_artifact_bundle
from .services.power_system_audit import build_power_system_source_audit, validate_power_system_source_audit
from .services.power_system_live_smoke import build_pjm_live_smoke_report, validate_power_system_source_readiness_report
from .services.power_system_locations import approved_pjm_location_pnode_ids
from .services.power_system_operational_events import (
    build_operational_event_candidate_plan,
    validate_operational_event_candidate_plan,
)
from .services.power_system_preflight import (
    DEFAULT_PJM_LOAD_FEEDS,
    DEFAULT_PJM_PRICE_FEEDS,
    build_pjm_ingestion_preflight_report,
    selected_pjm_data_miner_metadata_feeds,
)
from .services.power_system_raw_fetches import build_raw_source_fetch_manifest, validate_raw_source_fetch_manifests
from .services.power_system_source_metadata import (
    select_pjm_data_miner_metadata_expectations,
    verify_pjm_data_miner_definitions,
)
from .services.power_system_sources import build_power_system_source_publication_report
from .services.power_system_state import stage_power_system_bundle_candidate
from .services.source_query_plans import (
    build_pjm_generation_mix_query_requests,
    build_pjm_hourly_lmp_query_requests,
    build_pjm_load_query_requests,
    summarize_source_query_requests,
)
from .services.pnl import run_pnl_attribution
from .services.risk import read_historical_returns, run_historical_var
from .cache.hot_state import HotState
from .state.packs import build_candidate_state_pack, publish_candidate_state_pack
from .agent_runtime.capabilities import collect_agent_capabilities, collect_agent_doctor
from .agent_runtime.context_audit import audit_context_surfaces
from .agent_runtime.native_loop import run_native_agent_loop
from .agent_runtime.kb_validator import validate_knowledge_base
from .agent_runtime.release_workflow import collect_release_readiness
from .agent_runtime.vcs_workflow import collect_vcs_readiness
from .agent_runtime.work_item_loader import list_tickets, load_ticket, transition_ticket, validate_work_items
from .skills.validator import validate_skill_manifest
from .validation.reports import read_validation_report, render_regression_markdown, summarize_validation_report, write_validation_report
from .validation.runner import run_validation


def _cmd_validate_registries(args: argparse.Namespace) -> int:
    result = validate_registries(Path(args.registries), Path(args.schemas))
    print(f"validated {len(result.validated_files)} registry files; checked {result.checked_records} records")
    for warning in result.warnings:
        print(f"warning: {warning}")
    return 0


def _cmd_parse_period(args: argparse.Namespace) -> int:
    print(to_plain(parse_period(args.label, args.commodity)))
    return 0


def _cmd_normalize_prices(args: argparse.Namespace) -> int:
    points = normalize_marks(read_csv_rows(Path(args.input)))
    write_json(Path(args.output), points)
    print(f"wrote {len(points)} price points to {args.output}")
    return 0


def _cmd_normalize_positions(args: argparse.Namespace) -> int:
    marks = []
    if args.marks:
        for item in read_json(Path(args.marks)):
            from .models import PriceSurfacePoint

            marks.append(PriceSurfacePoint(**item))
    positions = normalize_positions(read_csv_rows(Path(args.positions)), marks)
    write_json(Path(args.output), positions)
    print(f"wrote {len(positions)} normalized positions to {args.output}")
    return 0


def _load_positions(path: Path):
    from .models import NormalizedPosition

    return [NormalizedPosition(**item) for item in read_json(path)]


def _cmd_run_pnl(args: argparse.Namespace) -> int:
    report = run_pnl_attribution(_load_positions(Path(args.prior)), _load_positions(Path(args.current)), args.run_id)
    write_json(Path(args.output), report)
    print(f"wrote PnL attribution to {args.output}")
    return 0


def _cmd_run_var(args: argparse.Namespace) -> int:
    report = run_historical_var(_load_positions(Path(args.positions)), read_historical_returns(Path(args.returns)), args.as_of, args.run_id)
    write_json(Path(args.output), report)
    print(f"wrote historical VaR to {args.output}")
    return 0


def _cmd_run_greeks(args: argparse.Namespace) -> int:
    report = run_black76_greeks(read_option_rows(Path(args.input)), args.run_id)
    write_json(Path(args.output), report)
    print(f"wrote Greeks to {args.output}")
    return 0


def _heatmap_price_surface_points(args: argparse.Namespace):
    if args.input:
        return read_price_surface_points(Path(args.input))
    if args.state_root:
        points = HotState(Path(args.state_root)).price_surface_points()
        if not points:
            raise WorkbenchException("HEATMAP_HOT_STATE_INPUT_MISSING", "HotState artifacts must include price_surface_points")
        return points
    raise WorkbenchException("HEATMAP_INPUT_REQUIRED", "--input or --state-root is required")


def _cmd_build_forward_price_heatmap(args: argparse.Namespace) -> int:
    report = build_forward_price_heatmap(
        _heatmap_price_surface_points(args),
        args.as_of,
        run_id=args.run_id,
        registry_dir=Path(args.registries),
    )
    validate_forward_price_heatmap(report, Path(args.schemas))
    write_json(Path(args.output), report)
    print(f"wrote forward price heatmap to {args.output}")
    return 0


def _read_pjm_load_fixture(path: Path, registry_dir: Path, as_of: str) -> tuple[list, list]:
    payload = read_json(path)
    feeds = payload.get("feeds") if isinstance(payload, dict) else None
    if not isinstance(feeds, dict):
        from .exceptions import WorkbenchException

        raise WorkbenchException("PJM_LOAD_FIXTURE_INVALID", "PJM load fixture must contain a feeds mapping")
    observations = []
    forecasts = []
    for feed_id, rows in feeds.items():
        if not isinstance(rows, list):
            from .exceptions import WorkbenchException

            raise WorkbenchException("PJM_LOAD_FIXTURE_INVALID", f"Feed {feed_id} rows must be a list")
        obs, fcst = normalize_pjm_fundamental_records(str(feed_id), [dict(item) for item in rows], registry_dir, as_of=as_of)
        observations.extend(obs)
        forecasts.extend(fcst)
    return observations, forecasts


def _dataminer_date_range(start: str, end: str) -> str:
    return f"{start} 00:00:00 to {end} 23:59:59"


def _fetch_live_pjm_load(args: argparse.Namespace, registry_dir: Path) -> tuple[list, list]:
    observations, forecasts, _manifests = _fetch_live_pjm_load_with_manifest(args, registry_dir)
    return observations, forecasts


def _fetch_live_pjm_load_with_manifest(args: argparse.Namespace, registry_dir: Path) -> tuple[list, list, list[dict[str, Any]]]:
    load_artemis_config(Path(args.repo_root))
    connector = PjmDataMinerConnector(base_url=args.base_url)
    observations = []
    forecasts = []
    manifests = []
    requested_feeds = args.feed or ["hrl_load_metered", "hrl_load_prelim", "load_frcstd_7_day", "load_frcstd_hist"]
    query_plan, query_requests = build_pjm_load_query_requests(
        registry_dir,
        args.start,
        args.end,
        requested_feeds,
        area=args.area,
        row_count=args.row_count,
        account_class=connector.account_class,
        paginate=not args.no_paginate,
        max_pages=args.max_pages,
    )
    query_summary = summarize_source_query_requests(query_plan, query_requests)
    for request_record in query_requests:
        result = connector.fetch(
            DataRequest(
                contract=request_record.registry_feed_id,
                as_of=args.as_of,
                parameters={
                    "feed": request_record.data_miner_feed,
                    "query": request_record.query,
                    "paginate": request_record.paginate,
                    "max_pages": request_record.max_pages,
                    "query_plan": request_record.query_plan,
                    "query_request": {
                        "request_id": request_record.request_id,
                        "request_kind": request_record.request_kind,
                        "registry_feed_id": request_record.registry_feed_id,
                        "pnode_id": request_record.pnode_id,
                        "window_start": request_record.window_start,
                        "window_end": request_record.window_end,
                    },
                    "query_execution_summary": query_summary,
                },
            )
        )
        manifests.append(
            build_raw_source_fetch_manifest(
                operator_id="PJM",
                source_system="pjm_data_miner_api",
                source_surface="load",
                request_record=request_record,
                result=result,
                query_execution_summary=query_summary,
            )
        )
        obs, fcst = normalize_pjm_fundamental_records(request_record.registry_feed_id, result.records, registry_dir, as_of=args.as_of)
        observations.extend(obs)
        forecasts.extend(fcst)
    return observations, forecasts, manifests


def _cmd_build_pjm_load_fundamentals(args: argparse.Namespace) -> int:
    registry_dir = Path(args.registries)
    if args.live:
        observations, forecasts, manifests = _fetch_live_pjm_load_with_manifest(args, registry_dir)
    else:
        if not args.input:
            from .exceptions import WorkbenchException

            raise WorkbenchException("PJM_LOAD_INPUT_REQUIRED", "--input is required unless --live is supplied")
        observations, forecasts = _read_pjm_load_fixture(Path(args.input), registry_dir, args.as_of)
        manifests = []
    artifacts = build_pjm_load_artifacts(observations, forecasts, args.as_of, run_id=args.run_id)
    if manifests:
        validate_raw_source_fetch_manifests(manifests, Path(args.schemas))
        artifacts["raw_source_fetch_manifests"] = manifests
    validate_fundamental_state(artifacts["pjm_load_fundamentals"], Path(args.schemas))
    write_json(Path(args.output), artifacts)
    print(f"wrote PJM load fundamentals artifacts to {args.output}")
    return 0


def _read_pjm_generation_mix_fixture(path: Path, registry_dir: Path, as_of: str) -> list:
    payload = read_json(path)
    feeds = payload.get("feeds") if isinstance(payload, dict) else None
    if not isinstance(feeds, dict):
        raise WorkbenchException("PJM_GENERATION_MIX_FIXTURE_INVALID", "PJM generation mix fixture must contain a feeds mapping")
    observations = []
    feed_map = {
        "gen_by_fuel": "PJM_GEN_BY_FUEL",
        "PJM_GEN_BY_FUEL": "PJM_GEN_BY_FUEL",
    }
    for fixture_feed, feed_id in feed_map.items():
        rows = feeds.get(fixture_feed)
        if rows is None:
            continue
        if not isinstance(rows, list):
            raise WorkbenchException("PJM_GENERATION_MIX_FIXTURE_INVALID", f"Feed {fixture_feed} rows must be a list")
        observations.extend(normalize_pjm_generation_mix_records(feed_id, [dict(item) for item in rows], registry_dir, as_of=as_of))
    return observations


def _fetch_live_pjm_generation_mix(args: argparse.Namespace, registry_dir: Path) -> list:
    observations, _manifests = _fetch_live_pjm_generation_mix_with_manifest(args, registry_dir)
    return observations


def _fetch_live_pjm_generation_mix_with_manifest(args: argparse.Namespace, registry_dir: Path) -> tuple[list, list[dict[str, Any]]]:
    load_artemis_config(Path(args.repo_root))
    connector = PjmDataMinerConnector(base_url=args.base_url)
    query_plan, query_requests = build_pjm_generation_mix_query_requests(
        registry_dir,
        args.start,
        args.end,
        row_count=args.row_count,
        account_class=connector.account_class,
        paginate=not args.no_paginate,
        max_pages=args.max_pages,
    )
    query_summary = summarize_source_query_requests(query_plan, query_requests)
    observations = []
    manifests = []
    for request_record in query_requests:
        result = connector.fetch(
            DataRequest(
                contract=request_record.registry_feed_id,
                as_of=args.as_of,
                parameters={
                    "feed": request_record.data_miner_feed,
                    "query": request_record.query,
                    "paginate": request_record.paginate,
                    "max_pages": request_record.max_pages,
                    "query_plan": request_record.query_plan,
                    "query_request": {
                        "request_id": request_record.request_id,
                        "request_kind": request_record.request_kind,
                        "registry_feed_id": request_record.registry_feed_id,
                        "pnode_id": request_record.pnode_id,
                        "window_start": request_record.window_start,
                        "window_end": request_record.window_end,
                    },
                    "query_execution_summary": query_summary,
                },
            )
        )
        manifests.append(
            build_raw_source_fetch_manifest(
                operator_id="PJM",
                source_system="pjm_data_miner_api",
                source_surface="generation_mix",
                request_record=request_record,
                result=result,
                query_execution_summary=query_summary,
            )
        )
        observations.extend(normalize_pjm_generation_mix_records(request_record.registry_feed_id, result.records, registry_dir, as_of=args.as_of))
    return observations, manifests


def _cmd_build_pjm_generation_mix(args: argparse.Namespace) -> int:
    registry_dir = Path(args.registries)
    if args.live:
        observations, manifests = _fetch_live_pjm_generation_mix_with_manifest(args, registry_dir)
    else:
        if not args.input:
            raise WorkbenchException("PJM_GENERATION_MIX_INPUT_REQUIRED", "--input is required unless --live is supplied")
        observations = _read_pjm_generation_mix_fixture(Path(args.input), registry_dir, args.as_of)
        manifests = []
    artifacts = build_pjm_generation_mix_artifacts(observations, args.as_of, run_id=args.run_id)
    if manifests:
        validate_raw_source_fetch_manifests(manifests, Path(args.schemas))
        artifacts["raw_source_fetch_manifests"] = manifests
    validate_generation_mix_state(artifacts["pjm_generation_mix"], Path(args.schemas))
    write_json(Path(args.output), artifacts)
    print(f"wrote PJM generation mix artifacts to {args.output}")
    return 0


def _read_pjm_lmp_fixture(path: Path, registry_dir: Path, as_of: str) -> tuple[list, list]:
    payload = read_json(path)
    feeds = payload.get("feeds") if isinstance(payload, dict) else None
    if not isinstance(feeds, dict):
        from .exceptions import WorkbenchException

        raise WorkbenchException("PJM_LMP_FIXTURE_INVALID", "PJM LMP fixture must contain a feeds mapping")
    pnodes = normalize_pjm_pnode_records([dict(item) for item in feeds.get("pnode", [])], registry_dir)
    observations = []
    feed_map = {
        "da_hrl_lmps": "PJM_DA_HOURLY_LMP",
        "rt_hrl_lmps": "PJM_RT_HOURLY_LMP",
        "PJM_DA_HOURLY_LMP": "PJM_DA_HOURLY_LMP",
        "PJM_RT_HOURLY_LMP": "PJM_RT_HOURLY_LMP",
    }
    for fixture_feed, feed_id in feed_map.items():
        rows = feeds.get(fixture_feed)
        if rows is None:
            continue
        if not isinstance(rows, list):
            from .exceptions import WorkbenchException

            raise WorkbenchException("PJM_LMP_FIXTURE_INVALID", f"Feed {fixture_feed} rows must be a list")
        observations.extend(normalize_pjm_lmp_records(feed_id, [dict(item) for item in rows], registry_dir, as_of=as_of))
    return pnodes, observations


def _pjm_pnode_ids_for_args(args: argparse.Namespace, registry_dir: Path) -> list[int]:
    approved_pnodes = approved_pjm_location_pnode_ids(registry_dir)
    ids = []
    for item in args.pnode_id or []:
        pnode_id = int(item)
        if pnode_id not in approved_pnodes:
            raise WorkbenchException("UNKNOWN_PJM_PNODE", f"Unsupported PJM pnode for approved power locations: {pnode_id}")
        ids.append(pnode_id)
    if args.location:
        locations = load_yaml_unique(registry_dir / "power_locations.yaml")
        for location in args.location:
            record = locations.get(str(location).upper())
            if not isinstance(record, dict) or record.get("pjm_pnode_id") is None:
                raise WorkbenchException("UNKNOWN_POWER_LOCATION", f"Unknown PJM power location with pnode mapping: {location}")
            ids.append(int(record["pjm_pnode_id"]))
    if not ids:
        raise WorkbenchException("PJM_LMP_PNODE_REQUIRED", "At least one --pnode-id or --location is required for live PJM LMP fetches")
    return sorted(set(ids))


def _fetch_live_pjm_lmp(args: argparse.Namespace, registry_dir: Path) -> tuple[list, list]:
    pnodes, observations, _manifests = _fetch_live_pjm_lmp_with_manifest(args, registry_dir)
    return pnodes, observations


def _fetch_live_pjm_lmp_with_manifest(args: argparse.Namespace, registry_dir: Path) -> tuple[list, list, list[dict[str, Any]]]:
    load_artemis_config(Path(args.repo_root))
    connector = PjmDataMinerConnector(base_url=args.base_url)
    pnode_ids = _pjm_pnode_ids_for_args(args, registry_dir)
    pnodes = []
    observations = []
    manifests = []
    requested_feeds = args.feed or ["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"]
    query_plan, query_requests = build_pjm_hourly_lmp_query_requests(
        registry_dir,
        args.start,
        args.end,
        requested_feeds,
        pnode_ids,
        row_count=args.row_count,
        account_class=connector.account_class,
        paginate=not args.no_paginate,
        max_pages=args.max_pages,
    )
    query_summary = summarize_source_query_requests(query_plan, query_requests)
    for request_record in query_requests:
        result = connector.fetch(
            DataRequest(
                contract=request_record.data_miner_feed,
                as_of=args.as_of,
                parameters={
                    "feed": request_record.data_miner_feed,
                    "query": request_record.query,
                    "paginate": request_record.paginate,
                    "max_pages": request_record.max_pages,
                    "query_plan": request_record.query_plan,
                    "query_request": {
                        "request_id": request_record.request_id,
                        "request_kind": request_record.request_kind,
                        "registry_feed_id": request_record.registry_feed_id,
                        "pnode_id": request_record.pnode_id,
                        "window_start": request_record.window_start,
                        "window_end": request_record.window_end,
                    },
                    "query_execution_summary": query_summary,
                },
            )
        )
        manifests.append(
            build_raw_source_fetch_manifest(
                operator_id="PJM",
                source_system="pjm_data_miner_api",
                source_surface="price",
                request_record=request_record,
                result=result,
                query_execution_summary=query_summary,
            )
        )
        if request_record.request_kind == "metadata":
            pnodes.extend(normalize_pjm_pnode_records(result.records, registry_dir))
        else:
            observations.extend(normalize_pjm_lmp_records(request_record.registry_feed_id, result.records, registry_dir, as_of=args.as_of))
    return pnodes, observations, manifests


def _cmd_build_pjm_lmp_prices(args: argparse.Namespace) -> int:
    registry_dir = Path(args.registries)
    if args.live:
        pnodes, observations, manifests = _fetch_live_pjm_lmp_with_manifest(args, registry_dir)
    else:
        if not args.input:
            from .exceptions import WorkbenchException

            raise WorkbenchException("PJM_LMP_INPUT_REQUIRED", "--input is required unless --live is supplied")
        pnodes, observations = _read_pjm_lmp_fixture(Path(args.input), registry_dir, args.as_of)
        manifests = []
    artifacts = build_pjm_power_price_artifacts(pnodes, observations, args.as_of, registry_dir, run_id=args.run_id)
    if manifests:
        validate_raw_source_fetch_manifests(manifests, Path(args.schemas))
        artifacts["raw_source_fetch_manifests"] = manifests
    validate_power_price_state(artifacts["pjm_power_prices"], Path(args.schemas))
    write_json(Path(args.output), artifacts)
    print(f"wrote PJM LMP price artifacts to {args.output}")
    return 0


def _read_price_points_payload(path: Path) -> list:
    payload = read_json(path)
    rows = payload.get("price_surface_points") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        from .exceptions import WorkbenchException

        raise WorkbenchException("PRICE_SURFACE_INPUT_INVALID", "Input must be a price_surface_points list or artifact containing price_surface_points")
    from .models import PriceSurfacePoint

    return [PriceSurfacePoint(**dict(item)) for item in rows]


def _cmd_rollup_power_price_shapes(args: argparse.Namespace) -> int:
    points = _read_price_points_payload(Path(args.input))
    artifacts = build_power_price_shape_artifacts(
        points,
        Path(args.registries),
        args.as_of,
        run_id=args.run_id,
        rule_ids=args.rule or None,
    )
    validate_power_price_shape_state(artifacts["power_price_shape_rollups"], Path(args.schemas))
    write_json(Path(args.output), artifacts)
    print(f"wrote power price shape rollups to {args.output}")
    return 0


def _namespace_with(args: argparse.Namespace, **updates: object) -> argparse.Namespace:
    values = vars(args).copy()
    values.update(updates)
    return argparse.Namespace(**values)


def _require_live_window(args: argparse.Namespace) -> None:
    if not args.start or not args.end:
        raise WorkbenchException("PJM_BUNDLE_LIVE_WINDOW_REQUIRED", "--start and --end are required for live PJM bundle builds")


def _read_preflight_input(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise WorkbenchException("PJM_PREFLIGHT_INPUT_INVALID", "PJM preflight input must be a mapping")
    return payload


def _read_source_readiness_input(path: Path, schema_dir: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise WorkbenchException("POWER_SYSTEM_SOURCE_READINESS_INPUT_INVALID", "Power-system source readiness input must be a mapping")
    validate_power_system_source_readiness_report(payload, schema_dir)
    return payload


def _read_operational_event_plan_input(path: Path, schema_dir: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise WorkbenchException("POWER_SYSTEM_OPERATIONAL_EVENT_PLAN_INPUT_INVALID", "Operational event plan input must be a mapping")
    validate_operational_event_candidate_plan(payload, schema_dir)
    return payload


def _build_bundle_preflight_report(args: argparse.Namespace, registry_dir: Path) -> dict[str, Any] | None:
    if args.preflight_input:
        report = _read_preflight_input(Path(args.preflight_input))
    elif args.live:
        load_artemis_config(Path(args.repo_root))
        connector = PjmDataMinerConnector(base_url=args.base_url)
        pnode_count = len(_pjm_pnode_ids_for_args(args, registry_dir))
        report = build_pjm_ingestion_preflight_report(
            registry_dir,
            api_key_configured=connector.available(),
            start=args.start,
            end=args.end,
            pnode_count=pnode_count,
            account_class=connector.account_class,
            load_feeds=args.load_feed or None,
            price_feeds=args.price_feed or None,
            include_generation_mix=True,
        )
    else:
        return None
    if args.require_ready_preflight and report.get("ready") is not True:
        raise WorkbenchException("PJM_PREFLIGHT_NOT_READY", f"PJM preflight blockers: {report.get('blockers') or []}")
    return report


def _build_bundle_source_readiness_report(args: argparse.Namespace, schema_dir: Path) -> dict[str, Any] | None:
    if args.source_readiness_input:
        report = _read_source_readiness_input(Path(args.source_readiness_input), schema_dir)
    else:
        if args.require_ready_source_readiness:
            raise WorkbenchException(
                "POWER_SYSTEM_SOURCE_READINESS_REQUIRED",
                "--source-readiness-input is required when --require-ready-source-readiness is supplied",
            )
        return None
    if args.require_ready_source_readiness and report.get("ready") is not True:
        raise WorkbenchException("POWER_SYSTEM_SOURCE_READINESS_NOT_READY", f"source readiness blockers: {report.get('blockers') or []}")
    return report


def _build_bundle_operational_event_plan(args: argparse.Namespace, registry_dir: Path, schema_dir: Path) -> dict[str, Any] | None:
    if args.operational_event_plan_input:
        plan = _read_operational_event_plan_input(Path(args.operational_event_plan_input), schema_dir)
    elif args.include_operational_event_plan:
        plan = build_operational_event_candidate_plan(registry_dir, operator_id="PJM")
        validate_operational_event_candidate_plan(plan, schema_dir)
    else:
        if args.require_approved_operational_events:
            raise WorkbenchException(
                "POWER_SYSTEM_OPERATIONAL_EVENT_PLAN_REQUIRED",
                "--operational-event-plan-input or --include-operational-event-plan is required when --require-approved-operational-events is supplied",
            )
        return None
    if args.require_approved_operational_events and plan.get("approved") is not True:
        raise WorkbenchException(
            "POWER_SYSTEM_OPERATIONAL_EVENTS_NOT_APPROVED",
            f"operational event blockers: {plan.get('publications') or []}",
        )
    return plan


def _selected_pjm_bundle_metadata_feeds(args: argparse.Namespace, registry_dir: Path) -> list[str]:
    return selected_pjm_data_miner_metadata_feeds(
        registry_dir,
        args.load_feed or DEFAULT_PJM_LOAD_FEEDS,
        args.price_feed or DEFAULT_PJM_PRICE_FEEDS,
        include_generation_mix=True,
    )


def _build_bundle_metadata_verification_report(args: argparse.Namespace, registry_dir: Path) -> dict[str, Any] | None:
    selected_feeds = _selected_pjm_bundle_metadata_feeds(args, registry_dir)
    if args.metadata_input:
        definitions = _definition_payloads_from_input(Path(args.metadata_input))
        definition_source = "fixture"
    elif args.live:
        connector = PjmDataMinerConnector(definition_base_url=args.definition_base_url)
        definitions = {feed: connector.fetch_definition(feed) for feed in selected_feeds}
        definition_source = "live_pjm_data_miner_definition"
    else:
        if args.require_metadata_verification:
            raise WorkbenchException(
                "PJM_METADATA_VERIFICATION_REQUIRED",
                "--metadata-input is required when --require-metadata-verification is supplied without --live",
            )
        return None
    report = verify_pjm_data_miner_definitions(
        definitions,
        registry_dir,
        feeds=selected_feeds,
        include_candidate=True,
    )
    report["definition_source"] = definition_source
    return report


def _build_bundle_source_publication_report(args: argparse.Namespace, registry_dir: Path) -> dict[str, Any]:
    selected_feed_ids = [
        *(args.load_feed or DEFAULT_PJM_LOAD_FEEDS),
        "PJM_PNODE",
        *(args.price_feed or DEFAULT_PJM_PRICE_FEEDS),
        "PJM_GEN_BY_FUEL",
    ]
    return build_power_system_source_publication_report(
        registry_dir,
        registry_feed_ids=selected_feed_ids,
        operator_id="PJM",
        source_system="pjm_data_miner_api",
    )


def _selected_pjm_load_pipeline_feed_ids(args: argparse.Namespace) -> list[str]:
    return list(args.load_feed or ["load_frcstd_7_day"])


def _pjm_load_data_miner_feed_ids(registry_dir: Path, feed_ids: list[str]) -> list[str]:
    feeds = load_pjm_fundamental_feeds(registry_dir)
    selected: list[str] = []
    for feed_id in feed_ids:
        feed = feeds.get(feed_id)
        if not isinstance(feed, dict):
            raise WorkbenchException("PJM_LOAD_PIPELINE_FEED_UNKNOWN", f"Unknown PJM load feed: {feed_id}")
        selected.append(str(feed["data_miner_feed"]))
    return selected


def _build_pjm_load_pipeline_preflight_report(args: argparse.Namespace, connector: PjmDataMinerConnector, feed_ids: list[str]) -> dict[str, Any]:
    blockers = []
    if not connector.available():
        blockers.append("ARTEMIS_PJM_API_KEY is not configured")
    if not args.start or not args.end:
        blockers.append("--start and --end are required")
    return {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "ready": not blockers,
        "blockers": blockers,
        "selected_feeds": {"load": list(feed_ids)},
        "credential_checks": {
            "ARTEMIS_PJM_API_KEY": {
                "configured": bool(connector.available()),
                "value_redacted": True,
            }
        },
        "contains_secret_values": False,
    }


def _build_pjm_load_pipeline_metadata_verification_report(
    args: argparse.Namespace,
    registry_dir: Path,
    feed_ids: list[str],
) -> dict[str, Any]:
    data_miner_feeds = _pjm_load_data_miner_feed_ids(registry_dir, feed_ids)
    if args.metadata_input:
        definitions = _definition_payloads_from_input(Path(args.metadata_input))
        definition_source = "fixture"
    else:
        connector = PjmDataMinerConnector(base_url=args.base_url, definition_base_url=args.definition_base_url)
        definitions = {feed: connector.fetch_definition(feed) for feed in data_miner_feeds}
        definition_source = "live_pjm_data_miner_definition"
    report = verify_pjm_data_miner_definitions(
        definitions,
        registry_dir,
        feeds=data_miner_feeds,
        include_candidate=True,
    )
    report["definition_source"] = definition_source
    return report


def _source_readiness_metadata_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "definition_source": report.get("definition_source"),
        "verified_feed_count": int(report.get("verified_feed_count") or 0),
        "verified_feeds": [
            {
                "registry_feed_id": item.get("registry_feed_id"),
                "data_miner_feed": item.get("data_miner_feed"),
                "required_field_count": int(item.get("required_field_count") or 0),
                "observed_field_count": int(item.get("observed_field_count") or 0),
            }
            for item in report.get("verified_feeds") or []
            if isinstance(item, dict)
        ],
        "contains_secret_values": False,
    }


def _build_pjm_load_pipeline_source_readiness_report(
    preflight_report: dict[str, Any],
    metadata_verification_report: dict[str, Any],
    manifests: list[dict[str, Any]],
    query_execution_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    blockers = list(preflight_report.get("blockers") or [])
    source_fetches = []
    for manifest in manifests:
        row_count = int(manifest.get("row_count") or 0)
        status = "success" if row_count > 0 else "empty"
        if status != "success":
            blockers.append(f"{manifest.get('registry_feed_id')}: no source rows returned")
        source_fetches.append(
            {
                "status": status,
                "product_family": "load",
                "registry_feed_id": str(manifest.get("registry_feed_id") or ""),
                "data_miner_feed": str(manifest.get("source_feed") or ""),
                "row_count": row_count,
                "page_count": int(manifest.get("page_count") or 0),
                "truncated_by_max_pages": bool(manifest.get("truncated_by_max_pages")),
            }
        )
    report = {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "ready": not blockers,
        "blockers": blockers,
        "preflight": {
            "ready": bool(preflight_report.get("ready")),
            "blocker_count": len(preflight_report.get("blockers") or []),
            "selected_feeds": dict(preflight_report.get("selected_feeds") or {}),
            "credential_checks": dict(preflight_report.get("credential_checks") or {}),
            "contains_secret_values": False,
        },
        "metadata_verification": _source_readiness_metadata_summary(metadata_verification_report),
        "source_fetches": source_fetches,
        "fetch_source_rows": True,
        "contains_secret_values": False,
    }
    if query_execution_summary is not None:
        report["query_execution"] = dict(query_execution_summary)
    return report


def _build_pjm_load_pipeline_bundle_payload(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    if not args.live:
        raise WorkbenchException("PJM_LOAD_PIPELINE_LIVE_REQUIRED", "--live is required for run-pjm-load-pipeline")
    _require_live_window(args)
    load_artemis_config(Path(args.repo_root))
    registry_dir = Path(args.registries)
    schema_dir = Path(args.schemas)
    feed_ids = _selected_pjm_load_pipeline_feed_ids(args)
    connector = PjmDataMinerConnector(base_url=args.base_url)
    preflight_report = _build_pjm_load_pipeline_preflight_report(args, connector, feed_ids)
    if preflight_report.get("ready") is not True:
        raise WorkbenchException("PJM_LOAD_PIPELINE_PREFLIGHT_NOT_READY", f"PJM load pipeline blockers: {preflight_report.get('blockers') or []}")

    metadata_verification_report = _build_pjm_load_pipeline_metadata_verification_report(args, registry_dir, feed_ids)
    observations, forecasts, raw_source_fetch_manifests = _fetch_live_pjm_load_with_manifest(
        _namespace_with(args, feed=feed_ids),
        registry_dir,
    )
    validate_raw_source_fetch_manifests(raw_source_fetch_manifests, schema_dir)
    query_execution_summary = None
    if raw_source_fetch_manifests:
        plan_id = raw_source_fetch_manifests[0].get("query_plan_id")
        for manifest in raw_source_fetch_manifests:
            if manifest.get("query_plan_id") != plan_id:
                continue
        query_execution_summary = {
            "plan_id": str(plan_id or "PJM_DATAMINER_LOAD_BOUNDED_INTERVAL"),
            "planned_request_count": len(raw_source_fetch_manifests),
            "built_request_count": len(raw_source_fetch_manifests),
            "account_class": connector.account_class,
            "max_connections_per_minute": connector._connection_limit(),
            "request_kinds": {
                "source_rows": len(raw_source_fetch_manifests),
            },
            "registry_feed_ids": sorted({str(item.get("registry_feed_id")) for item in raw_source_fetch_manifests}),
            "pnode_ids": [],
            "date_windows": [{"start": args.start, "end": args.end}],
            "contains_secret_values": False,
        }
    source_readiness_report = _build_pjm_load_pipeline_source_readiness_report(
        preflight_report,
        metadata_verification_report,
        raw_source_fetch_manifests,
        query_execution_summary,
    )
    validate_power_system_source_readiness_report(source_readiness_report, schema_dir)
    if source_readiness_report.get("ready") is not True:
        raise WorkbenchException("PJM_LOAD_PIPELINE_SOURCE_NOT_READY", f"PJM load source readiness blockers: {source_readiness_report.get('blockers') or []}")

    load_artifacts = build_pjm_load_artifacts(observations, forecasts, args.as_of, run_id=f"{args.run_id}-load")
    validate_fundamental_state(load_artifacts["pjm_load_fundamentals"], schema_dir)
    source_publication_report = build_power_system_source_publication_report(
        registry_dir,
        registry_feed_ids=feed_ids,
        operator_id="PJM",
        source_system="pjm_data_miner_api",
    )
    bundle = build_power_system_artifact_bundle(
        load_artifacts,
        {"raw_source_fetch_manifests": raw_source_fetch_manifests},
        bundle_id=args.run_id,
        as_of=args.as_of,
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        data_environment=args.data_environment,
        preflight_report=preflight_report,
        metadata_verification_report=metadata_verification_report,
        source_readiness_report=source_readiness_report,
        source_publication_report=source_publication_report,
    )
    return bundle, {
        "feed_ids": feed_ids,
        "metadata_verification_report": metadata_verification_report,
        "source_readiness_report": source_readiness_report,
    }


def _build_pjm_morning_bundle_payload(args: argparse.Namespace) -> dict[str, Any]:
    registry_dir = Path(args.registries)
    schema_dir = Path(args.schemas)
    preflight_report = _build_bundle_preflight_report(args, registry_dir)
    metadata_verification_report = _build_bundle_metadata_verification_report(args, registry_dir)
    source_readiness_report = _build_bundle_source_readiness_report(args, schema_dir)
    source_publication_report = _build_bundle_source_publication_report(args, registry_dir)
    operational_event_plan = _build_bundle_operational_event_plan(args, registry_dir, schema_dir)
    raw_source_fetch_manifests: list[dict[str, Any]] = []
    if args.live:
        if preflight_report and preflight_report.get("ready") is not True:
            raise WorkbenchException("PJM_PREFLIGHT_NOT_READY", f"PJM preflight blockers: {preflight_report.get('blockers') or []}")
        _require_live_window(args)
        observations, forecasts, load_manifests = _fetch_live_pjm_load_with_manifest(_namespace_with(args, feed=args.load_feed), registry_dir)
        generation_observations, generation_manifests = _fetch_live_pjm_generation_mix_with_manifest(args, registry_dir)
        pnodes, lmp_observations, price_manifests = _fetch_live_pjm_lmp_with_manifest(_namespace_with(args, feed=args.price_feed), registry_dir)
        raw_source_fetch_manifests = [*load_manifests, *generation_manifests, *price_manifests]
        validate_raw_source_fetch_manifests(raw_source_fetch_manifests, schema_dir)
    else:
        if not args.load_input or not args.generation_input or not args.lmp_input:
            raise WorkbenchException(
                "PJM_BUNDLE_INPUT_REQUIRED",
                "--load-input, --generation-input, and --lmp-input are required unless --live is supplied",
            )
        observations, forecasts = _read_pjm_load_fixture(Path(args.load_input), registry_dir, args.as_of)
        generation_observations = _read_pjm_generation_mix_fixture(Path(args.generation_input), registry_dir, args.as_of)
        pnodes, lmp_observations = _read_pjm_lmp_fixture(Path(args.lmp_input), registry_dir, args.as_of)

    load_artifacts = build_pjm_load_artifacts(observations, forecasts, args.as_of, run_id=f"{args.run_id}-load")
    validate_fundamental_state(load_artifacts["pjm_load_fundamentals"], schema_dir)

    generation_artifacts = build_pjm_generation_mix_artifacts(generation_observations, args.as_of, run_id=f"{args.run_id}-generation")
    validate_generation_mix_state(generation_artifacts["pjm_generation_mix"], schema_dir)

    price_artifacts = build_pjm_power_price_artifacts(pnodes, lmp_observations, args.as_of, registry_dir, run_id=f"{args.run_id}-prices")
    validate_power_price_state(price_artifacts["pjm_power_prices"], schema_dir)

    from .models import PriceSurfacePoint

    hourly_price_points = [PriceSurfacePoint(**item) for item in price_artifacts["price_surface_points"]]
    shape_artifacts = build_power_price_shape_artifacts(
        hourly_price_points,
        registry_dir,
        args.as_of,
        run_id=f"{args.run_id}-shapes",
        rule_ids=args.shape_rule or None,
    )
    validate_power_price_shape_state(shape_artifacts["power_price_shape_rollups"], schema_dir)

    payloads = [load_artifacts, generation_artifacts, price_artifacts, shape_artifacts]
    if raw_source_fetch_manifests:
        payloads.append({"raw_source_fetch_manifests": raw_source_fetch_manifests})
    bundle = build_power_system_artifact_bundle(
        *payloads,
        bundle_id=args.run_id,
        as_of=args.as_of,
        operator_id="PJM",
        source_system="pjm_data_miner_api",
        data_environment=args.data_environment,
        preflight_report=preflight_report,
        metadata_verification_report=metadata_verification_report,
        source_readiness_report=source_readiness_report,
        source_publication_report=source_publication_report,
        operational_event_plan=operational_event_plan,
    )
    return bundle


def _cmd_build_pjm_morning_bundle(args: argparse.Namespace) -> int:
    bundle = _build_pjm_morning_bundle_payload(args)
    write_json(Path(args.output), bundle)
    print(f"wrote PJM morning artifact bundle to {args.output}")
    return 0


def _cmd_compose_artifacts(args: argparse.Namespace) -> int:
    payloads = [read_json(Path(path)) for path in args.input]
    write_json(Path(args.output), compose_artifact_payloads(*payloads))
    print(f"wrote composed artifacts to {args.output}")
    return 0


def _cmd_build_state_pack(args: argparse.Namespace) -> int:
    artifacts = read_json(Path(args.artifacts))
    manifest = RunManifest(run_id=args.run_id, created_at=utc_now_iso(), agent_pack_version="0.1.0", inputs=[{"path": args.artifacts}])
    build_candidate_state_pack(Path(args.state_root), args.run_id, args.as_of, artifacts, manifest, synthetic=args.synthetic)
    if args.publish:
        publish_candidate_state_pack(Path(args.state_root), args.run_id, shared_readonly=args.shared_readonly)
        print(f"published state pack {args.run_id}")
    else:
        print(f"built candidate state pack {args.run_id}")
    return 0


def _cmd_stage_power_system_bundle_candidate(args: argparse.Namespace) -> int:
    bundle = read_json(Path(args.bundle))
    result = stage_power_system_bundle_candidate(
        bundle,
        Path(args.state_root),
        args.state_id,
        as_of=args.as_of,
        input_path=args.bundle,
    )
    if args.output:
        write_json(Path(args.output), result)
        print(f"wrote staged power-system state candidate report to {args.output}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_power_system_source_audit(args: argparse.Namespace) -> int:
    if args.bundle:
        bundle = read_json(Path(args.bundle))
    elif args.state_root:
        bundle = HotState(Path(args.state_root)).artifacts()
    else:
        raise WorkbenchException("POWER_SYSTEM_SOURCE_AUDIT_INPUT_REQUIRED", "--bundle or --state-root is required")
    audit = build_power_system_source_audit(bundle)
    validate_power_system_source_audit(audit, Path(args.schemas))
    if args.output:
        write_json(Path(args.output), audit)
        print(f"wrote power-system source audit to {args.output}")
    else:
        print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["ready"] or args.allow_blockers else 1


def _bundle_source_readiness_summary(bundle: dict[str, Any]) -> dict[str, Any] | None:
    metadata = bundle.get("power_system_artifact_bundle")
    if not isinstance(metadata, dict):
        return None
    readiness = metadata.get("source_readiness")
    if not isinstance(readiness, dict):
        return None
    summary = {
        "ready": bool(readiness.get("ready")),
        "blocker_count": int(readiness.get("blocker_count") or 0),
        "fetch_source_rows": bool(readiness.get("fetch_source_rows")),
        "source_fetch_statuses": [
            {
                "data_miner_feed": item.get("data_miner_feed"),
                "status": item.get("status"),
                "row_count": int(item.get("row_count") or 0),
            }
            for item in readiness.get("source_fetches") or []
            if isinstance(item, dict)
        ],
    }
    if readiness.get("query_execution") is not None:
        summary["query_execution"] = readiness.get("query_execution")
    return summary


def _bundle_source_publication_summary(bundle: dict[str, Any]) -> dict[str, Any] | None:
    metadata = bundle.get("power_system_artifact_bundle")
    if not isinstance(metadata, dict):
        return None
    publications = metadata.get("source_publications")
    if not isinstance(publications, dict):
        return None
    return {
        "publication_count": int(publications.get("publication_count") or 0),
        "source_publication_statuses": [
            {
                "publication_id": item.get("publication_id"),
                "status": item.get("status"),
                "authoritative_use": (item.get("publication_lifecycle") or {}).get("authoritative_use")
                if isinstance(item.get("publication_lifecycle"), dict)
                else None,
            }
            for item in publications.get("source_publications") or []
            if isinstance(item, dict)
        ],
    }


def _bundle_raw_source_fetch_summary(bundle: dict[str, Any]) -> dict[str, Any] | None:
    metadata = bundle.get("power_system_artifact_bundle")
    if not isinstance(metadata, dict):
        return None
    raw_fetches = metadata.get("raw_source_fetches")
    if not isinstance(raw_fetches, dict):
        return None
    return {
        "manifest_count": int(raw_fetches.get("manifest_count") or 0),
        "total_row_count": int(raw_fetches.get("total_row_count") or 0),
        "total_page_count": int(raw_fetches.get("total_page_count") or 0),
        "truncated_manifest_count": int(raw_fetches.get("truncated_manifest_count") or 0),
        "source_surface_counts": dict(raw_fetches.get("source_surface_counts") or {}),
        "registry_feed_ids": list(raw_fetches.get("registry_feed_ids") or []),
        "query_plan_ids": list(raw_fetches.get("query_plan_ids") or []),
    }


def _bundle_operational_event_plan_summary(bundle: dict[str, Any]) -> dict[str, Any] | None:
    metadata = bundle.get("power_system_artifact_bundle")
    if not isinstance(metadata, dict):
        return None
    plan = metadata.get("operational_event_plan")
    if not isinstance(plan, dict):
        return None
    return {
        "approved": bool(plan.get("approved")),
        "publication_count": int(plan.get("publication_count") or 0),
        "feed_count": int(plan.get("feed_count") or 0),
        "blocked_publication_count": int(plan.get("blocked_publication_count") or 0),
        "blocked_feed_count": int(plan.get("blocked_feed_count") or 0),
        "publication_statuses": [
            {
                "publication_id": item.get("publication_id"),
                "approved": bool(item.get("approved")),
                "authoritative_use": item.get("authoritative_use"),
            }
            for item in plan.get("publications") or []
            if isinstance(item, dict)
        ],
    }


def _cmd_run_pjm_morning_pipeline(args: argparse.Namespace) -> int:
    bundle = _build_pjm_morning_bundle_payload(args)
    write_json(Path(args.output), bundle)
    stage_result = stage_power_system_bundle_candidate(
        bundle,
        Path(args.state_root),
        args.state_id,
        as_of=args.as_of,
        input_path=args.output,
    )
    report = {
        "pipeline_id": args.run_id,
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "bundle_output": args.output,
        "stage": stage_result,
        "source_readiness": _bundle_source_readiness_summary(bundle),
        "source_publications": _bundle_source_publication_summary(bundle),
        "raw_source_fetches": _bundle_raw_source_fetch_summary(bundle),
        "operational_event_plan": _bundle_operational_event_plan_summary(bundle),
        "published": False,
    }
    if args.pipeline_output:
        write_json(Path(args.pipeline_output), report)
        print(f"wrote PJM morning pipeline report to {args.pipeline_output}")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _cmd_run_pjm_load_pipeline(args: argparse.Namespace) -> int:
    bundle, pipeline_inputs = _build_pjm_load_pipeline_bundle_payload(args)
    write_json(Path(args.output), bundle)
    stage_result = stage_power_system_bundle_candidate(
        bundle,
        Path(args.state_root),
        args.state_id,
        as_of=args.as_of,
        input_path=args.output,
    )
    published = False
    if args.publish:
        publish_candidate_state_pack(Path(args.state_root), args.state_id, shared_readonly=args.shared_readonly)
        published = True
    report = {
        "pipeline_id": args.run_id,
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "feed_ids": list(pipeline_inputs["feed_ids"]),
        "bundle_output": args.output,
        "stage": stage_result,
        "source_readiness": _bundle_source_readiness_summary(bundle),
        "source_publications": _bundle_source_publication_summary(bundle),
        "raw_source_fetches": _bundle_raw_source_fetch_summary(bundle),
        "metadata_verification": {
            "definition_source": pipeline_inputs["metadata_verification_report"].get("definition_source"),
            "verified_feed_count": pipeline_inputs["metadata_verification_report"].get("verified_feed_count"),
        },
        "published": published,
    }
    if args.pipeline_output:
        write_json(Path(args.pipeline_output), report)
        print(f"wrote PJM load pipeline report to {args.pipeline_output}")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _cmd_work_context(args: argparse.Namespace) -> int:
    context = collect_development_context(Path(args.repo_root), args.ticket, Path(args.config) if args.config else None)
    context["compatibility_command"] = "pga work-context"
    if args.output:
        write_json(Path(args.output), context)
        print(f"wrote work context for {args.ticket} to {args.output}")
    else:
        import json

        print(json.dumps(context, indent=2, sort_keys=True))
    return 0


def _cmd_validate_work_items(args: argparse.Namespace) -> int:
    validated = validate_work_items(Path(args.work_root), Path(args.schemas))
    print(f"validated {len(validated)} work items")
    return 0


def _cmd_validate_kb(args: argparse.Namespace) -> int:
    result = validate_knowledge_base(Path(args.kb_root), Path(args.schemas))
    print(f"validated knowledge base manifest with {result['entries']} entries")
    return 0


def _cmd_agent_capabilities(args: argparse.Namespace) -> int:
    capabilities = collect_agent_capabilities(Path(args.repo_root), check_network=args.check_network)
    if args.json:
        print(json.dumps(capabilities, indent=2, sort_keys=True))
    else:
        print(f"recommended_mode: {capabilities['recommended_mode']}")
        for name, item in sorted((capabilities.get("core") or {}).items()):
            status = "available" if item.get("available") else "missing"
            print(f"core.{name}: {status}")
        for name, item in sorted((capabilities.get("wrappers") or {}).items()):
            status = "available" if item.get("available") else "missing"
            suffix = ""
            if "reachable" in item:
                suffix = f", reachable={bool(item.get('reachable'))}"
            print(f"wrapper.{name}: {status}, required={bool(item.get('required'))}{suffix}")
    return 0 if (capabilities.get("core") or {}).get("pga", {}).get("available") else 1


def _cmd_agent_doctor(args: argparse.Namespace) -> int:
    result = collect_agent_doctor(Path(args.repo_root), check_network=args.check_network, skip_tests=args.skip_tests)
    if args.json:
        print(json.dumps(to_plain(result), indent=2, sort_keys=True))
    else:
        for check in result["checks"]:
            status = "skipped" if check.get("skipped") else "passed" if check.get("passed") else "failed"
            print(f"{check['name']}: {status}")
        print(f"recommended_mode: {result['capabilities']['recommended_mode']}")
    return 0 if result["passed"] else 1


def _cmd_vcs_ready(args: argparse.Namespace) -> int:
    result = collect_vcs_readiness(
        Path(args.repo_root),
        args.ticket,
        target_branch=args.target_branch,
        remote=args.remote,
        skip_tests=args.skip_tests,
    )
    if args.json:
        print(json.dumps(to_plain(result), indent=2, sort_keys=True))
    else:
        print(f"ticket: {result['ticket_id']} ({result['ticket_status']})")
        print(f"branch: {result['current_branch']}")
        print(f"expected_branch: {result['expected_branch']}")
        print(f"target_branch: {result['target_branch']}")
        print(f"validation_passed: {result['validation_passed']}")
        print(f"ready_for_commit: {result['ready_for_commit']}")
        print(f"ready_for_merge: {result['ready_for_merge']}")
        for warning in result["warnings"]:
            print(f"warning: {warning}")
        print("standard_commands:")
        for command in result["standard_commands"]:
            print(f"- {command}")
    return 0 if result["ready_for_commit"] else 1


def _cmd_release_check(args: argparse.Namespace) -> int:
    result = collect_release_readiness(
        Path(args.repo_root),
        ticket_id=args.ticket,
        skip_tests=args.skip_tests,
        validation_report=Path(args.validation_report) if getattr(args, "validation_report", None) else None,
    )
    if args.json:
        print(json.dumps(to_plain(result), indent=2, sort_keys=True))
    else:
        package = result["package"]
        print(f"package: {package.get('name')} {package.get('version')}")
        print(f"requires_python: {package.get('requires_python')}")
        print(f"validation_skipped: {result['validation_skipped']}")
        print(f"validation_passed: {result['validation_passed']}")
        print(f"ready_for_release_prep: {result['ready_for_release_prep']}")
        for blocker in result.get("blockers") or []:
            print(f"blocker: {blocker}")
        print("validation_commands:")
        for item in result.get("validation_results") or []:
            status = "skipped" if item.get("skipped") else "passed" if item.get("passed") else "failed"
            print(f"- {item['command']}: {status}")
        print("planning_bridge:")
        for path, exists in result["planning_bridge"].items():
            print(f"- {path}: {'present' if exists else 'missing'}")
        regression = result["regression_report"]
        print(f"regression_report: {regression.get('path')} ({regression.get('test_count')} tests)")
        print("required_release_note_fields:")
        for field in result["required_release_note_fields"]:
            print(f"- {field}")
    return 0 if args.skip_tests or result["ready_for_release_prep"] else 1


def _default_validation_outputs(repo_root: Path, ticket_id: str | None, generated_at: str) -> list[Path]:
    stamp = generated_at.replace(":", "").replace("-", "")
    if ticket_id:
        root = repo_root / "development" / "validation_reports" / ticket_id
        return [root / "latest.json", root / f"{stamp}_validation.json"]
    root = repo_root / "development" / "validation_reports"
    return [root / "latest.json", root / f"{stamp}_validation.json"]


def _cmd_validate(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root)
    report = run_validation(repo_root, ticket_id=args.ticket, strict=args.strict)
    if args.output:
        write_validation_report(report, Path(args.output))
    else:
        for path in _default_validation_outputs(repo_root, args.ticket, report.generated_at):
            write_validation_report(report, path)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"validation_status: {report.overall_status}")
        print(f"strict: {report.strict}")
        for check in report.checks:
            print(f"- {check.check_id}: {check.status}")
        for warning in report.warnings:
            print(f"warning: {warning}")
        for error in report.errors:
            print(f"error: {error}")
    return 0 if report.overall_status == "passed" else 1


def _cmd_validate_report(args: argparse.Namespace) -> int:
    report = read_validation_report(Path(args.input))
    if args.markdown:
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(render_regression_markdown(report), encoding="utf-8")
        print(f"wrote regression report to {args.markdown}")
    elif args.json:
        print(json.dumps(summarize_validation_report(report), indent=2, sort_keys=True))
    else:
        summary = summarize_validation_report(report)
        print(f"report_id: {summary['report_id']}")
        print(f"validation_status: {summary['overall_status']}")
        for check in summary["checks"]:
            print(f"- {check['check_id']}: {check['status']}")
    return 0 if report.overall_status == "passed" else 1


def _cmd_work_list(args: argparse.Namespace) -> int:
    tickets = list_tickets(Path(args.work_root))
    if args.json:
        print(json.dumps(tickets, indent=2, sort_keys=True))
    else:
        for ticket in tickets:
            print(f"{ticket['id']}: {ticket['status']} - {ticket['title']}")
    return 0


def _cmd_work_show(args: argparse.Namespace) -> int:
    ticket = load_ticket(Path(args.work_root), args.ticket)
    if args.json:
        print(json.dumps(ticket, indent=2, sort_keys=True))
    else:
        print(yaml.safe_dump(ticket, sort_keys=False))
    return 0


def _cmd_work_validate(args: argparse.Namespace) -> int:
    validated = validate_work_items(Path(args.work_root), Path(args.schemas))
    print(f"validated {len(validated)} work items")
    return 0


def _cmd_work_transition(args: argparse.Namespace) -> int:
    ticket = transition_ticket(
        Path(args.work_root),
        args.ticket,
        args.status,
        timestamp=utc_now_iso(),
        validation_report=args.validation_report,
        regression_report=args.regression_report,
        reviewed_by=args.reviewed_by,
        review_summary=args.review_summary,
        blocked_reason=args.blocked_reason,
        superseded_by=args.superseded_by,
    )
    print(f"{ticket['id']}: {ticket['status']}")
    return 0


def _cmd_dev_loop(args: argparse.Namespace) -> int:
    report = run_native_agent_loop(
        Path(args.repo_root),
        args.ticket,
        backend=args.backend,
        instruction=args.instruction,
        dry_run=args.dry_run,
        run_backend=args.run_backend,
        output=Path(args.output) if args.output else None,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"ticket: {report['ticket_id']}")
        print(f"backend: {report['backend']}")
        print(f"context_path: {report['context_path']}")
        print(f"backend_command: {report.get('backend_command') or 'manual'}")
        print(f"backend_ran: {report['backend_ran']}")
        if report.get("validation_report"):
            print(f"validation_report: {report['validation_report']}")
    return 0 if not report.get("errors") else 1


def _cmd_artemis_config_show(args: argparse.Namespace) -> int:
    config = load_artemis_config(Path(args.repo_root), Path(args.config) if args.config else None)
    if args.json:
        print(json.dumps(config, indent=2, sort_keys=True))
    else:
        print(dump_config_yaml(config))
    return 0


def _cmd_artemis_config_validate(args: argparse.Namespace) -> int:
    config = validate_artemis_config(Path(args.repo_root), Path(args.config) if args.config else None)
    print(f"validated artemis config {config['name']} {config['version']}")
    return 0


def _cmd_artemis_capabilities(args: argparse.Namespace) -> int:
    capabilities = collect_artemis_capabilities(
        Path(args.repo_root),
        check_network=args.check_network,
        config_path=Path(args.config) if args.config else None,
    )
    if args.json:
        print(json.dumps(capabilities, indent=2, sort_keys=True))
    else:
        print(f"artemis: {capabilities['version']}")
        print(f"recommended_mode: {capabilities['recommended_mode']}")
        print("modes:")
        for mode_name in sorted(capabilities.get("modes") or {}):
            mode = capabilities["modes"][mode_name]
            print(f"- {mode_name}: can_modify_repo={bool(mode.get('can_modify_repo'))}")
        print(f"tools: {capabilities['tools']['count']}")
        for tool_id, policy in sorted((capabilities["tools"].get("policy") or {}).items()):
            print(f"- {tool_id}: risk={policy['risk']}, modes={','.join(policy['modes'])}")
    return 0


def _cmd_context_audit(args: argparse.Namespace) -> int:
    result = audit_context_surfaces(Path(args.repo_root))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "passed" if result["passed"] else "failed"
        print(f"context_audit: {status}")
        for finding in result.get("findings") or []:
            print(f"- {finding['severity']} {finding['code']} {finding['path']}: {finding['message']}")
    return 0 if result["passed"] else 1


def _analyst_view_input_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload = read_json(Path(args.input)) if args.input else {}
    if args.state_root:
        hot = HotState(Path(args.state_root))
        current_state = hot.load_current()
        if not payload:
            payload = {
                "as_of": str(args.as_of or current_state["as_of"])[:10],
                "data_environment": "development",
            }
        payload = merge_hot_state_artifacts(payload, dict(current_state.get("artifacts") or {}))
    if not payload:
        raise WorkbenchException("ANALYST_VIEW_INPUT_REQUIRED", "--input or --state-root is required")
    return payload


def _cmd_analyst_view_build(args: argparse.Namespace) -> int:
    payload = _analyst_view_input_payload(args)
    view = build_view(
        Path(args.repo_root),
        args.template,
        payload,
        as_of=args.as_of,
        allow_fixture=args.allow_fixture,
    )
    write_json(Path(args.output), view)
    print(f"wrote {view['view_type']} view to {args.output}")
    return 0


def _cmd_data_sources_list(args: argparse.Namespace) -> int:
    payload = validate_data_sources(Path(args.registry), Path(args.schemas))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for source_id, item in sorted((payload.get("data_sources") or {}).items()):
            print(f"{source_id}: kind={item['kind']}, required={bool(item['required'])}")
    return 0


def _cmd_data_sources_validate(args: argparse.Namespace) -> int:
    payload = validate_data_sources(Path(args.registry), Path(args.schemas))
    env_names = credential_env_names(payload)
    print(f"validated {len(payload.get('data_sources') or {})} data sources; credential_env_names={len(env_names)}")
    return 0


def _definition_payloads_from_input(path: Path) -> dict[str, dict[str, object]]:
    payload = read_json(path)
    feeds = payload.get("feeds") if isinstance(payload, dict) else None
    source = feeds if isinstance(feeds, dict) else payload
    if not isinstance(source, dict):
        raise WorkbenchException("PJM_METADATA_INPUT_INVALID", "PJM metadata input must be a mapping or contain a feeds mapping")
    definitions: dict[str, dict[str, object]] = {}
    for feed, definition in source.items():
        if not isinstance(definition, dict):
            raise WorkbenchException("PJM_METADATA_INPUT_INVALID", f"PJM metadata definition for {feed} must be a mapping")
        definitions[str(feed)] = dict(definition)
    return definitions


def _cmd_verify_pjm_source_metadata(args: argparse.Namespace) -> int:
    registry_dir = Path(args.registries)
    feeds = args.feed or None
    if args.live:
        connector = PjmDataMinerConnector(definition_base_url=args.definition_base_url)
        selected = select_pjm_data_miner_metadata_expectations(registry_dir, feeds=feeds, include_candidate=args.include_candidate)
        definitions = {feed: connector.fetch_definition(feed) for feed in sorted(selected)}
        definition_source = "live_pjm_data_miner_definition"
    else:
        if not args.input:
            raise WorkbenchException("PJM_METADATA_INPUT_REQUIRED", "--input is required unless --live is supplied")
        definitions = _definition_payloads_from_input(Path(args.input))
        definition_source = "fixture"
    report = verify_pjm_data_miner_definitions(
        definitions,
        registry_dir,
        feeds=feeds,
        include_candidate=args.include_candidate,
    )
    report["definition_source"] = definition_source
    if args.output:
        write_json(Path(args.output), report)
        print(f"wrote PJM source metadata verification report to {args.output}")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _cmd_pjm_ingestion_preflight(args: argparse.Namespace) -> int:
    load_artemis_config(Path(args.repo_root))
    registry_dir = Path(args.registries)
    pnode_ids = []
    if args.location or args.pnode_id:
        pnode_ids = _pjm_pnode_ids_for_args(args, registry_dir)
    report = build_pjm_ingestion_preflight_report(
        registry_dir,
        api_key_configured=bool(PjmDataMinerConnector().available()),
        start=args.start,
        end=args.end,
        pnode_count=len(pnode_ids),
        account_class=args.account_class or PjmDataMinerConnector().account_class,
        load_feeds=args.load_feed or None,
        price_feeds=args.price_feed or None,
        include_generation_mix=not args.no_generation_mix,
    )
    if args.output:
        write_json(Path(args.output), report)
        print(f"wrote PJM ingestion preflight report to {args.output}")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] or args.allow_blockers else 1


def _pjm_pnode_ids_for_optional_args(args: argparse.Namespace, registry_dir: Path) -> list[int]:
    if args.location or args.pnode_id:
        return _pjm_pnode_ids_for_args(args, registry_dir)
    return []


def _cmd_pjm_live_smoke(args: argparse.Namespace) -> int:
    load_artemis_config(Path(args.repo_root))
    registry_dir = Path(args.registries)
    connector = PjmDataMinerConnector(
        base_url=args.base_url,
        definition_base_url=args.definition_base_url,
        timeout_seconds=args.timeout_seconds,
    )
    report = build_pjm_live_smoke_report(
        registry_dir,
        connector,
        start=args.start,
        end=args.end,
        pnode_ids=_pjm_pnode_ids_for_optional_args(args, registry_dir),
        load_feeds=args.load_feed or None,
        price_feeds=args.price_feed or None,
        include_generation_mix=not args.no_generation_mix,
        fetch_source_rows=not args.metadata_only,
        row_count=args.row_count,
    )
    validate_power_system_source_readiness_report(report, Path(args.schemas))
    if args.output:
        write_json(Path(args.output), report)
        print(f"wrote PJM live smoke report to {args.output}")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] or args.allow_blockers else 1


def _cmd_pjm_operational_event_candidate_plan(args: argparse.Namespace) -> int:
    plan = build_operational_event_candidate_plan(Path(args.registries), operator_id=args.operator_id)
    validate_operational_event_candidate_plan(plan, Path(args.schemas))
    if args.output:
        write_json(Path(args.output), plan)
        print(f"wrote PJM operational event candidate plan to {args.output}")
    else:
        print(json.dumps(plan, indent=2, sort_keys=True))
    return 0 if plan["approved"] or not args.require_approved else 1


def _cmd_skill_validate(args: argparse.Namespace) -> int:
    result = validate_skill_manifest(Path(args.repo_root), Path(args.schemas))
    print(f"validated {result['skills']} skills; procedural_skills={result.get('procedural_skills', 0)}")
    return 0


def _cmd_views_validate(args: argparse.Namespace) -> int:
    result = validate_view_manifest(Path(args.repo_root), Path(args.schemas))
    print(f"validated {result['templates']} view templates")
    return 0


def _cmd_dev_context(args: argparse.Namespace) -> int:
    context = collect_development_context(Path(args.repo_root), args.ticket, Path(args.config) if args.config else None)
    if args.output:
        write_json(Path(args.output), context)
        print(f"wrote development context for {args.ticket} to {args.output}")
    else:
        print(json.dumps(context, indent=2, sort_keys=True))
    return 0


def _cmd_dev_plan(args: argparse.Namespace) -> int:
    context = collect_development_context(Path(args.repo_root), args.ticket, Path(args.config) if args.config else None)
    ticket = context["ticket"]
    print(f"ticket: {ticket['id']}")
    print(f"title: {ticket['title']}")
    print("tasks:")
    for task in ticket.get("tasks") or []:
        print(f"- {task}")
    return 0


def _cmd_dev_propose(args: argparse.Namespace) -> int:
    validate_coding_backends(Path(args.repo_root))
    print(f"proposal request accepted for {args.ticket}; backend={args.backend}; repo mutation remains approval-gated")
    return 0


def _cmd_release_candidate(args: argparse.Namespace) -> int:
    candidate = build_release_candidate(Path(args.repo_root), args.ticket, target_version=args.target_version)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(yaml.safe_dump(candidate, sort_keys=False), encoding="utf-8")
        print(f"wrote release candidate to {args.output}")
    else:
        print(yaml.safe_dump(candidate, sort_keys=False))
    return 0


def _add_pjm_morning_bundle_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--load-input")
    parser.add_argument("--generation-input")
    parser.add_argument("--lmp-input")
    parser.add_argument("--preflight-input")
    parser.add_argument("--require-ready-preflight", action="store_true")
    parser.add_argument("--metadata-input")
    parser.add_argument("--require-metadata-verification", action="store_true")
    parser.add_argument("--source-readiness-input")
    parser.add_argument("--require-ready-source-readiness", action="store_true")
    parser.add_argument("--operational-event-plan-input")
    parser.add_argument("--include-operational-event-plan", action="store_true")
    parser.add_argument("--require-approved-operational-events", action="store_true")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--area")
    parser.add_argument("--load-feed", action="append", choices=["hrl_load_metered", "hrl_load_prelim", "load_frcstd_7_day", "load_frcstd_hist"], default=[])
    parser.add_argument("--location", action="append", default=[])
    parser.add_argument("--pnode-id", action="append", default=[])
    parser.add_argument("--price-feed", action="append", choices=["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"], default=[])
    parser.add_argument("--shape-rule", action="append", choices=["PJM_DAILY_PEAK_HE_0800_2300_EPT", "PJM_DAILY_OFFPEAK_5X8_2X24_EPT", "PJM_DAILY_ATC_24H_EPT"], default=[])
    parser.add_argument("--row-count", type=int, default=50000)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--no-paginate", action="store_true")
    parser.add_argument("--base-url")
    parser.add_argument("--definition-base-url")
    parser.add_argument("--run-id", default="pjm-morning-bundle")
    parser.add_argument("--data-environment", default="production")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--registries", default="registries")
    parser.add_argument("--schemas", default="schemas")
    parser.set_defaults(func=_cmd_build_pjm_morning_bundle)


def _add_pjm_source_metadata_verify_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--feed", action="append", default=[])
    parser.add_argument("--include-candidate", action="store_true")
    parser.add_argument("--definition-base-url")
    parser.add_argument("--registries", default="registries")
    parser.set_defaults(func=_cmd_verify_pjm_source_metadata)


def _add_pjm_ingestion_preflight_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--location", action="append", default=[])
    parser.add_argument("--pnode-id", action="append", default=[])
    parser.add_argument("--load-feed", action="append", choices=["hrl_load_metered", "hrl_load_prelim", "load_frcstd_7_day", "load_frcstd_hist"], default=[])
    parser.add_argument("--price-feed", action="append", choices=["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"], default=[])
    parser.add_argument("--account-class", choices=["non_member", "member"])
    parser.add_argument("--no-generation-mix", action="store_true")
    parser.add_argument("--allow-blockers", action="store_true")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--registries", default="registries")
    parser.set_defaults(func=_cmd_pjm_ingestion_preflight)


def _add_pjm_live_smoke_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--location", action="append", default=[])
    parser.add_argument("--pnode-id", action="append", default=[])
    parser.add_argument("--load-feed", action="append", choices=["hrl_load_metered", "hrl_load_prelim", "load_frcstd_7_day", "load_frcstd_hist"], default=[])
    parser.add_argument("--price-feed", action="append", choices=["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"], default=[])
    parser.add_argument("--no-generation-mix", action="store_true")
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--row-count", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--base-url")
    parser.add_argument("--definition-base-url")
    parser.add_argument("--allow-blockers", action="store_true")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--registries", default="registries")
    parser.add_argument("--schemas", default="schemas")
    parser.set_defaults(func=_cmd_pjm_live_smoke)


def _add_pjm_operational_event_candidate_plan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output")
    parser.add_argument("--operator-id", default="PJM")
    parser.add_argument("--require-approved", action="store_true")
    parser.add_argument("--registries", default="registries")
    parser.add_argument("--schemas", default="schemas")
    parser.set_defaults(func=_cmd_pjm_operational_event_candidate_plan)


def _add_stage_power_system_bundle_candidate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--state-id", required=True)
    parser.add_argument("--as-of")
    parser.add_argument("--output")
    parser.set_defaults(func=_cmd_stage_power_system_bundle_candidate)


def _add_power_system_source_audit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bundle")
    parser.add_argument("--state-root")
    parser.add_argument("--output")
    parser.add_argument("--allow-blockers", action="store_true")
    parser.add_argument("--schemas", default="schemas")
    parser.set_defaults(func=_cmd_power_system_source_audit)


def _add_pjm_morning_pipeline_args(parser: argparse.ArgumentParser) -> None:
    _add_pjm_morning_bundle_args(parser)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--state-id", required=True)
    parser.add_argument("--pipeline-output")
    parser.set_defaults(func=_cmd_run_pjm_morning_pipeline)


def _add_pjm_load_pipeline_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--area")
    parser.add_argument("--load-feed", action="append", choices=["hrl_load_metered", "hrl_load_prelim", "load_frcstd_7_day", "load_frcstd_hist"], default=[])
    parser.add_argument("--metadata-input")
    parser.add_argument("--row-count", type=int, default=50000)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--no-paginate", action="store_true")
    parser.add_argument("--base-url")
    parser.add_argument("--definition-base-url")
    parser.add_argument("--run-id", default="pjm-load-pipeline")
    parser.add_argument("--data-environment", default="production")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--registries", default="registries")
    parser.add_argument("--schemas", default="schemas")
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--state-id", required=True)
    parser.add_argument("--pipeline-output")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--shared-readonly", action="store_true")
    parser.set_defaults(func=_cmd_run_pjm_load_pipeline)


def build_parser(prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog or Path(sys.argv[0]).name or "artemis")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--ticket")
    p.add_argument("--output")
    p.add_argument("--json", action="store_true")
    validate_sub = p.add_subparsers(dest="validate_command")
    vr = validate_sub.add_parser("report")
    vr.add_argument("--input", required=True)
    vr.add_argument("--markdown")
    vr.add_argument("--json", action="store_true")
    vr.set_defaults(func=_cmd_validate_report)
    p.set_defaults(func=_cmd_validate)

    p = sub.add_parser("validate-registries")
    p.add_argument("--registries", default="registries")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_validate_registries)

    p = sub.add_parser("parse-period")
    p.add_argument("label")
    p.add_argument("--commodity", default="generic", choices=["generic", "power", "gas"])
    p.set_defaults(func=_cmd_parse_period)

    p = sub.add_parser("normalize-prices")
    p.add_argument("--input")
    p.add_argument("--state-root")
    p.add_argument("--output", required=True)
    p.set_defaults(func=_cmd_normalize_prices)

    p = sub.add_parser("normalize-positions")
    p.add_argument("--positions", required=True)
    p.add_argument("--marks")
    p.add_argument("--output", required=True)
    p.set_defaults(func=_cmd_normalize_positions)

    p = sub.add_parser("run-pnl-attribution")
    p.add_argument("--prior", required=True)
    p.add_argument("--current", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--run-id", default="pnl-run")
    p.set_defaults(func=_cmd_run_pnl)

    p = sub.add_parser("run-var")
    p.add_argument("--positions", required=True)
    p.add_argument("--returns", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--run-id", default="var-run")
    p.set_defaults(func=_cmd_run_var)

    p = sub.add_parser("run-greeks")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--run-id", default="greeks-run")
    p.set_defaults(func=_cmd_run_greeks)

    p = sub.add_parser("build-forward-price-heatmap")
    p.add_argument("--input")
    p.add_argument("--state-root")
    p.add_argument("--as-of", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--run-id", default="forward-price-heatmap")
    p.add_argument("--registries", default="registries")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_build_forward_price_heatmap)

    p = sub.add_parser("build-pjm-load-fundamentals")
    p.add_argument("--as-of", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--input")
    p.add_argument("--live", action="store_true")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--area")
    p.add_argument("--feed", action="append", choices=["hrl_load_metered", "hrl_load_prelim", "load_frcstd_7_day", "load_frcstd_hist"], default=[])
    p.add_argument("--row-count", type=int, default=50000)
    p.add_argument("--max-pages", type=int, default=1)
    p.add_argument("--no-paginate", action="store_true")
    p.add_argument("--base-url")
    p.add_argument("--run-id", default="pjm-load-fundamentals")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--registries", default="registries")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_build_pjm_load_fundamentals)

    p = sub.add_parser("build-pjm-generation-mix")
    p.add_argument("--as-of", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--input")
    p.add_argument("--live", action="store_true")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--row-count", type=int, default=50000)
    p.add_argument("--max-pages", type=int, default=1)
    p.add_argument("--no-paginate", action="store_true")
    p.add_argument("--base-url")
    p.add_argument("--run-id", default="pjm-generation-mix")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--registries", default="registries")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_build_pjm_generation_mix)

    p = sub.add_parser("build-pjm-lmp-prices")
    p.add_argument("--as-of", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--input")
    p.add_argument("--live", action="store_true")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--location", action="append", default=[])
    p.add_argument("--pnode-id", action="append", default=[])
    p.add_argument("--feed", action="append", choices=["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"], default=[])
    p.add_argument("--row-count", type=int, default=50000)
    p.add_argument("--max-pages", type=int, default=1)
    p.add_argument("--no-paginate", action="store_true")
    p.add_argument("--base-url")
    p.add_argument("--run-id", default="pjm-power-prices")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--registries", default="registries")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_build_pjm_lmp_prices)

    p = sub.add_parser("build-pjm-morning-bundle")
    _add_pjm_morning_bundle_args(p)

    p = sub.add_parser("run-pjm-morning-pipeline")
    _add_pjm_morning_pipeline_args(p)

    p = sub.add_parser("run-pjm-load-pipeline")
    _add_pjm_load_pipeline_args(p)

    p = sub.add_parser("verify-pjm-source-metadata")
    _add_pjm_source_metadata_verify_args(p)

    p = sub.add_parser("pjm-ingestion-preflight")
    _add_pjm_ingestion_preflight_args(p)

    p = sub.add_parser("pjm-live-smoke")
    _add_pjm_live_smoke_args(p)
    p = sub.add_parser("pjm-operational-event-plan")
    _add_pjm_operational_event_candidate_plan_args(p)

    p = sub.add_parser("rollup-power-price-shapes")
    p.add_argument("--input", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--rule", action="append", choices=["PJM_DAILY_PEAK_HE_0800_2300_EPT", "PJM_DAILY_OFFPEAK_5X8_2X24_EPT", "PJM_DAILY_ATC_24H_EPT"], default=[])
    p.add_argument("--run-id", default="power-price-shape-rollup")
    p.add_argument("--registries", default="registries")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_rollup_power_price_shapes)

    p = sub.add_parser("compose-artifacts")
    p.add_argument("--input", action="append", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=_cmd_compose_artifacts)

    p = sub.add_parser("stage-power-system-bundle-candidate")
    _add_stage_power_system_bundle_candidate_args(p)
    p = sub.add_parser("power-system-source-audit")
    _add_power_system_source_audit_args(p)

    p = sub.add_parser("build-state-pack")
    p.add_argument("--state-root", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--artifacts", required=True)
    p.add_argument("--publish", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--shared-readonly", action="store_true")
    p.set_defaults(func=_cmd_build_state_pack)

    p = sub.add_parser("work-context")
    p.add_argument("--ticket", required=True)
    p.add_argument("--config")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--output")
    p.set_defaults(func=_cmd_work_context)

    p = sub.add_parser("validate-work-items")
    p.add_argument("--work-root", default="work")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_validate_work_items)

    p = sub.add_parser("work")
    work_sub = p.add_subparsers(dest="work_command", required=True)
    w = work_sub.add_parser("list")
    w.add_argument("--work-root", default="work")
    w.add_argument("--json", action="store_true")
    w.set_defaults(func=_cmd_work_list)
    w = work_sub.add_parser("show")
    w.add_argument("ticket")
    w.add_argument("--work-root", default="work")
    w.add_argument("--json", action="store_true")
    w.set_defaults(func=_cmd_work_show)
    w = work_sub.add_parser("validate")
    w.add_argument("--work-root", default="work")
    w.add_argument("--schemas", default="schemas")
    w.set_defaults(func=_cmd_work_validate)
    w = work_sub.add_parser("transition")
    w.add_argument("ticket")
    w.add_argument("status", choices=["active", "implemented", "validated", "closed", "blocked", "superseded"])
    w.add_argument("--work-root", default="work")
    w.add_argument("--validation-report")
    w.add_argument("--regression-report")
    w.add_argument("--reviewed-by")
    w.add_argument("--review-summary")
    w.add_argument("--blocked-reason")
    w.add_argument("--superseded-by")
    w.set_defaults(func=_cmd_work_transition)

    p = sub.add_parser("validate-kb")
    p.add_argument("--kb-root", default="knowledge_base")
    p.add_argument("--schemas", default="schemas")
    p.set_defaults(func=_cmd_validate_kb)

    p = sub.add_parser("agent-capabilities")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--check-network", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_agent_capabilities)

    p = sub.add_parser("agent-doctor")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--check-network", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--skip-tests", action="store_true")
    p.set_defaults(func=_cmd_agent_doctor)

    p = sub.add_parser("vcs-ready")
    p.add_argument("--ticket", required=True)
    p.add_argument("--repo-root", default=".")
    p.add_argument("--target-branch", default="main")
    p.add_argument("--remote", default="origin")
    p.add_argument("--skip-tests", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_vcs_ready)

    p = sub.add_parser("release-check")
    p.add_argument("--ticket")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--validation-report")
    p.add_argument("--skip-tests", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_release_check)

    p = sub.add_parser("capabilities")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--config")
    p.add_argument("--check-network", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_artemis_capabilities)

    p = sub.add_parser("context")
    context_sub = p.add_subparsers(dest="context_command", required=True)
    audit = context_sub.add_parser("audit")
    audit.add_argument("--repo-root", default=".")
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(func=_cmd_context_audit)

    p = sub.add_parser("config")
    config_sub = p.add_subparsers(dest="config_command", required=True)
    c = config_sub.add_parser("show")
    c.add_argument("--repo-root", default=".")
    c.add_argument("--config")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=_cmd_artemis_config_show)
    c = config_sub.add_parser("validate")
    c.add_argument("--repo-root", default=".")
    c.add_argument("--config")
    c.set_defaults(func=_cmd_artemis_config_validate)

    p = sub.add_parser("analyst")
    analyst_sub = p.add_subparsers(dest="analyst_command", required=True)
    view = analyst_sub.add_parser("view")
    view_sub = view.add_subparsers(dest="view_command", required=True)
    b = view_sub.add_parser("build")
    b.add_argument("--template", required=True)
    b.add_argument("--as-of")
    b.add_argument("--input")
    b.add_argument("--output", required=True)
    b.add_argument("--state-root")
    b.add_argument("--repo-root", default=".")
    b.add_argument("--allow-fixture", action="store_true")
    b.set_defaults(func=_cmd_analyst_view_build)
    heatmap = analyst_sub.add_parser("heatmap")
    heatmap_sub = heatmap.add_subparsers(dest="heatmap_command", required=True)
    h = heatmap_sub.add_parser("build")
    h.add_argument("--input")
    h.add_argument("--state-root")
    h.add_argument("--as-of", required=True)
    h.add_argument("--output", required=True)
    h.add_argument("--run-id", default="forward-price-heatmap")
    h.add_argument("--registries", default="registries")
    h.add_argument("--schemas", default="schemas")
    h.set_defaults(func=_cmd_build_forward_price_heatmap)
    fundamentals = analyst_sub.add_parser("fundamentals")
    fundamentals_sub = fundamentals.add_subparsers(dest="fundamentals_command", required=True)
    f = fundamentals_sub.add_parser("build-pjm-load")
    f.add_argument("--as-of", required=True)
    f.add_argument("--output", required=True)
    f.add_argument("--input")
    f.add_argument("--live", action="store_true")
    f.add_argument("--start", required=True)
    f.add_argument("--end", required=True)
    f.add_argument("--area")
    f.add_argument("--feed", action="append", choices=["hrl_load_metered", "hrl_load_prelim", "load_frcstd_7_day", "load_frcstd_hist"], default=[])
    f.add_argument("--row-count", type=int, default=50000)
    f.add_argument("--max-pages", type=int, default=1)
    f.add_argument("--no-paginate", action="store_true")
    f.add_argument("--base-url")
    f.add_argument("--run-id", default="pjm-load-fundamentals")
    f.add_argument("--repo-root", default=".")
    f.add_argument("--registries", default="registries")
    f.add_argument("--schemas", default="schemas")
    f.set_defaults(func=_cmd_build_pjm_load_fundamentals)
    g = fundamentals_sub.add_parser("build-pjm-generation-mix")
    g.add_argument("--as-of", required=True)
    g.add_argument("--output", required=True)
    g.add_argument("--input")
    g.add_argument("--live", action="store_true")
    g.add_argument("--start", required=True)
    g.add_argument("--end", required=True)
    g.add_argument("--row-count", type=int, default=50000)
    g.add_argument("--max-pages", type=int, default=1)
    g.add_argument("--no-paginate", action="store_true")
    g.add_argument("--base-url")
    g.add_argument("--run-id", default="pjm-generation-mix")
    g.add_argument("--repo-root", default=".")
    g.add_argument("--registries", default="registries")
    g.add_argument("--schemas", default="schemas")
    g.set_defaults(func=_cmd_build_pjm_generation_mix)
    prices = analyst_sub.add_parser("prices")
    prices_sub = prices.add_subparsers(dest="prices_command", required=True)
    pr = prices_sub.add_parser("build-pjm-lmp")
    pr.add_argument("--as-of", required=True)
    pr.add_argument("--output", required=True)
    pr.add_argument("--input")
    pr.add_argument("--live", action="store_true")
    pr.add_argument("--start", required=True)
    pr.add_argument("--end", required=True)
    pr.add_argument("--location", action="append", default=[])
    pr.add_argument("--pnode-id", action="append", default=[])
    pr.add_argument("--feed", action="append", choices=["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"], default=[])
    pr.add_argument("--row-count", type=int, default=50000)
    pr.add_argument("--max-pages", type=int, default=1)
    pr.add_argument("--no-paginate", action="store_true")
    pr.add_argument("--base-url")
    pr.add_argument("--run-id", default="pjm-power-prices")
    pr.add_argument("--repo-root", default=".")
    pr.add_argument("--registries", default="registries")
    pr.add_argument("--schemas", default="schemas")
    pr.set_defaults(func=_cmd_build_pjm_lmp_prices)
    sh = prices_sub.add_parser("rollup-shapes")
    sh.add_argument("--input", required=True)
    sh.add_argument("--as-of", required=True)
    sh.add_argument("--output", required=True)
    sh.add_argument("--rule", action="append", choices=["PJM_DAILY_PEAK_HE_0800_2300_EPT", "PJM_DAILY_OFFPEAK_5X8_2X24_EPT", "PJM_DAILY_ATC_24H_EPT"], default=[])
    sh.add_argument("--run-id", default="power-price-shape-rollup")
    sh.add_argument("--registries", default="registries")
    sh.add_argument("--schemas", default="schemas")
    sh.set_defaults(func=_cmd_rollup_power_price_shapes)
    bundle = analyst_sub.add_parser("bundle")
    bundle_sub = bundle.add_subparsers(dest="bundle_command", required=True)
    mb = bundle_sub.add_parser("build-pjm-morning")
    _add_pjm_morning_bundle_args(mb)
    rp = bundle_sub.add_parser("run-pjm-morning-pipeline")
    _add_pjm_morning_pipeline_args(rp)
    lp = bundle_sub.add_parser("run-pjm-load-pipeline")
    _add_pjm_load_pipeline_args(lp)
    sc = bundle_sub.add_parser("stage-state-candidate")
    _add_stage_power_system_bundle_candidate_args(sc)
    sa = bundle_sub.add_parser("source-audit")
    _add_power_system_source_audit_args(sa)

    p = sub.add_parser("data-sources")
    ds_sub = p.add_subparsers(dest="data_sources_command", required=True)
    d = ds_sub.add_parser("list")
    d.add_argument("--registry", default="registries/data_sources.yaml")
    d.add_argument("--schemas", default="schemas")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=_cmd_data_sources_list)
    d = ds_sub.add_parser("validate")
    d.add_argument("--registry", default="registries/data_sources.yaml")
    d.add_argument("--schemas", default="schemas")
    d.set_defaults(func=_cmd_data_sources_validate)
    d = ds_sub.add_parser("verify-pjm-metadata")
    _add_pjm_source_metadata_verify_args(d)
    d = ds_sub.add_parser("pjm-preflight")
    _add_pjm_ingestion_preflight_args(d)
    d = ds_sub.add_parser("pjm-live-smoke")
    _add_pjm_live_smoke_args(d)
    d = ds_sub.add_parser("pjm-operational-event-plan")
    _add_pjm_operational_event_candidate_plan_args(d)

    p = sub.add_parser("skill")
    skill_sub = p.add_subparsers(dest="skill_command", required=True)
    s = skill_sub.add_parser("validate")
    s.add_argument("--repo-root", default=".")
    s.add_argument("--schemas", default="schemas")
    s.set_defaults(func=_cmd_skill_validate)

    p = sub.add_parser("views")
    views_sub = p.add_subparsers(dest="views_command", required=True)
    v = views_sub.add_parser("validate")
    v.add_argument("--repo-root", default=".")
    v.add_argument("--schemas", default="schemas")
    v.set_defaults(func=_cmd_views_validate)

    p = sub.add_parser("dev")
    dev_sub = p.add_subparsers(dest="dev_command", required=True)
    d = dev_sub.add_parser("context")
    d.add_argument("--ticket", required=True)
    d.add_argument("--repo-root", default=".")
    d.add_argument("--config")
    d.add_argument("--output")
    d.set_defaults(func=_cmd_dev_context)
    d = dev_sub.add_parser("plan")
    d.add_argument("--ticket", required=True)
    d.add_argument("--repo-root", default=".")
    d.add_argument("--config")
    d.set_defaults(func=_cmd_dev_plan)
    d = dev_sub.add_parser("propose")
    d.add_argument("--ticket", required=True)
    d.add_argument("--backend", default="human")
    d.add_argument("--repo-root", default=".")
    d.set_defaults(func=_cmd_dev_propose)
    d = dev_sub.add_parser("loop")
    d.add_argument("--ticket", required=True)
    d.add_argument("--backend", default="manual")
    d.add_argument("--instruction")
    d.add_argument("--repo-root", default=".")
    d.add_argument("--dry-run", action="store_true")
    d.add_argument("--run-backend", action="store_true")
    d.add_argument("--output")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=_cmd_dev_loop)

    p = sub.add_parser("release")
    release_sub = p.add_subparsers(dest="release_command", required=True)
    r = release_sub.add_parser("check")
    r.add_argument("--ticket")
    r.add_argument("--repo-root", default=".")
    r.add_argument("--validation-report")
    r.add_argument("--skip-tests", action="store_true")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=_cmd_release_check)
    r = release_sub.add_parser("candidate")
    r.add_argument("--ticket", required=True)
    r.add_argument("--repo-root", default=".")
    r.add_argument("--target-version", default="0.2.0")
    r.add_argument("--output")
    r.set_defaults(func=_cmd_release_candidate)

    return parser


def build_artemis_parser(prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog or "artemis")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--ticket")
    p.add_argument("--output")
    p.add_argument("--json", action="store_true")
    validate_sub = p.add_subparsers(dest="validate_command")
    vr = validate_sub.add_parser("report")
    vr.add_argument("--input", required=True)
    vr.add_argument("--markdown")
    vr.add_argument("--json", action="store_true")
    vr.set_defaults(func=_cmd_validate_report)
    p.set_defaults(func=_cmd_validate)

    p = sub.add_parser("parse-period")
    p.add_argument("label")
    p.add_argument("--commodity", default="generic", choices=["generic", "power", "gas"])
    p.set_defaults(func=_cmd_parse_period)

    p = sub.add_parser("capabilities")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--config")
    p.add_argument("--check-network", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_artemis_capabilities)

    p = sub.add_parser("context")
    context_sub = p.add_subparsers(dest="context_command", required=True)
    audit = context_sub.add_parser("audit")
    audit.add_argument("--repo-root", default=".")
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(func=_cmd_context_audit)

    p = sub.add_parser("config")
    config_sub = p.add_subparsers(dest="config_command", required=True)
    c = config_sub.add_parser("show")
    c.add_argument("--repo-root", default=".")
    c.add_argument("--config")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=_cmd_artemis_config_show)
    c = config_sub.add_parser("validate")
    c.add_argument("--repo-root", default=".")
    c.add_argument("--config")
    c.set_defaults(func=_cmd_artemis_config_validate)

    p = sub.add_parser("analyst")
    analyst_sub = p.add_subparsers(dest="analyst_command", required=True)
    view = analyst_sub.add_parser("view")
    view_sub = view.add_subparsers(dest="view_command", required=True)
    b = view_sub.add_parser("build")
    b.add_argument("--template", required=True)
    b.add_argument("--as-of")
    b.add_argument("--input")
    b.add_argument("--output", required=True)
    b.add_argument("--state-root")
    b.add_argument("--repo-root", default=".")
    b.add_argument("--allow-fixture", action="store_true")
    b.set_defaults(func=_cmd_analyst_view_build)
    heatmap = analyst_sub.add_parser("heatmap")
    heatmap_sub = heatmap.add_subparsers(dest="heatmap_command", required=True)
    h = heatmap_sub.add_parser("build")
    h.add_argument("--input")
    h.add_argument("--state-root")
    h.add_argument("--as-of", required=True)
    h.add_argument("--output", required=True)
    h.add_argument("--run-id", default="forward-price-heatmap")
    h.add_argument("--registries", default="registries")
    h.add_argument("--schemas", default="schemas")
    h.set_defaults(func=_cmd_build_forward_price_heatmap)
    fundamentals = analyst_sub.add_parser("fundamentals")
    fundamentals_sub = fundamentals.add_subparsers(dest="fundamentals_command", required=True)
    f = fundamentals_sub.add_parser("build-pjm-load")
    f.add_argument("--as-of", required=True)
    f.add_argument("--output", required=True)
    f.add_argument("--input")
    f.add_argument("--live", action="store_true")
    f.add_argument("--start", required=True)
    f.add_argument("--end", required=True)
    f.add_argument("--area")
    f.add_argument("--feed", action="append", choices=["hrl_load_metered", "hrl_load_prelim", "load_frcstd_7_day", "load_frcstd_hist"], default=[])
    f.add_argument("--row-count", type=int, default=50000)
    f.add_argument("--max-pages", type=int, default=1)
    f.add_argument("--no-paginate", action="store_true")
    f.add_argument("--base-url")
    f.add_argument("--run-id", default="pjm-load-fundamentals")
    f.add_argument("--repo-root", default=".")
    f.add_argument("--registries", default="registries")
    f.add_argument("--schemas", default="schemas")
    f.set_defaults(func=_cmd_build_pjm_load_fundamentals)
    g = fundamentals_sub.add_parser("build-pjm-generation-mix")
    g.add_argument("--as-of", required=True)
    g.add_argument("--output", required=True)
    g.add_argument("--input")
    g.add_argument("--live", action="store_true")
    g.add_argument("--start", required=True)
    g.add_argument("--end", required=True)
    g.add_argument("--row-count", type=int, default=50000)
    g.add_argument("--max-pages", type=int, default=1)
    g.add_argument("--no-paginate", action="store_true")
    g.add_argument("--base-url")
    g.add_argument("--run-id", default="pjm-generation-mix")
    g.add_argument("--repo-root", default=".")
    g.add_argument("--registries", default="registries")
    g.add_argument("--schemas", default="schemas")
    g.set_defaults(func=_cmd_build_pjm_generation_mix)
    prices = analyst_sub.add_parser("prices")
    prices_sub = prices.add_subparsers(dest="prices_command", required=True)
    pr = prices_sub.add_parser("build-pjm-lmp")
    pr.add_argument("--as-of", required=True)
    pr.add_argument("--output", required=True)
    pr.add_argument("--input")
    pr.add_argument("--live", action="store_true")
    pr.add_argument("--start", required=True)
    pr.add_argument("--end", required=True)
    pr.add_argument("--location", action="append", default=[])
    pr.add_argument("--pnode-id", action="append", default=[])
    pr.add_argument("--feed", action="append", choices=["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"], default=[])
    pr.add_argument("--row-count", type=int, default=50000)
    pr.add_argument("--max-pages", type=int, default=1)
    pr.add_argument("--no-paginate", action="store_true")
    pr.add_argument("--base-url")
    pr.add_argument("--run-id", default="pjm-power-prices")
    pr.add_argument("--repo-root", default=".")
    pr.add_argument("--registries", default="registries")
    pr.add_argument("--schemas", default="schemas")
    pr.set_defaults(func=_cmd_build_pjm_lmp_prices)
    sh = prices_sub.add_parser("rollup-shapes")
    sh.add_argument("--input", required=True)
    sh.add_argument("--as-of", required=True)
    sh.add_argument("--output", required=True)
    sh.add_argument("--rule", action="append", choices=["PJM_DAILY_PEAK_HE_0800_2300_EPT", "PJM_DAILY_OFFPEAK_5X8_2X24_EPT", "PJM_DAILY_ATC_24H_EPT"], default=[])
    sh.add_argument("--run-id", default="power-price-shape-rollup")
    sh.add_argument("--registries", default="registries")
    sh.add_argument("--schemas", default="schemas")
    sh.set_defaults(func=_cmd_rollup_power_price_shapes)
    bundle = analyst_sub.add_parser("bundle")
    bundle_sub = bundle.add_subparsers(dest="bundle_command", required=True)
    mb = bundle_sub.add_parser("build-pjm-morning")
    _add_pjm_morning_bundle_args(mb)
    rp = bundle_sub.add_parser("run-pjm-morning-pipeline")
    _add_pjm_morning_pipeline_args(rp)
    lp = bundle_sub.add_parser("run-pjm-load-pipeline")
    _add_pjm_load_pipeline_args(lp)
    sc = bundle_sub.add_parser("stage-state-candidate")
    _add_stage_power_system_bundle_candidate_args(sc)
    sa = bundle_sub.add_parser("source-audit")
    _add_power_system_source_audit_args(sa)

    p = sub.add_parser("data-sources")
    ds_sub = p.add_subparsers(dest="data_sources_command", required=True)
    d = ds_sub.add_parser("list")
    d.add_argument("--registry", default="registries/data_sources.yaml")
    d.add_argument("--schemas", default="schemas")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=_cmd_data_sources_list)
    d = ds_sub.add_parser("validate")
    d.add_argument("--registry", default="registries/data_sources.yaml")
    d.add_argument("--schemas", default="schemas")
    d.set_defaults(func=_cmd_data_sources_validate)
    d = ds_sub.add_parser("verify-pjm-metadata")
    _add_pjm_source_metadata_verify_args(d)
    d = ds_sub.add_parser("pjm-preflight")
    _add_pjm_ingestion_preflight_args(d)
    d = ds_sub.add_parser("pjm-live-smoke")
    _add_pjm_live_smoke_args(d)
    d = ds_sub.add_parser("pjm-operational-event-plan")
    _add_pjm_operational_event_candidate_plan_args(d)

    p = sub.add_parser("skill")
    skill_sub = p.add_subparsers(dest="skill_command", required=True)
    s = skill_sub.add_parser("validate")
    s.add_argument("--repo-root", default=".")
    s.add_argument("--schemas", default="schemas")
    s.set_defaults(func=_cmd_skill_validate)

    p = sub.add_parser("views")
    views_sub = p.add_subparsers(dest="views_command", required=True)
    v = views_sub.add_parser("validate")
    v.add_argument("--repo-root", default=".")
    v.add_argument("--schemas", default="schemas")
    v.set_defaults(func=_cmd_views_validate)

    p = sub.add_parser("work")
    work_sub = p.add_subparsers(dest="work_command", required=True)
    w = work_sub.add_parser("list")
    w.add_argument("--work-root", default="work")
    w.add_argument("--json", action="store_true")
    w.set_defaults(func=_cmd_work_list)
    w = work_sub.add_parser("show")
    w.add_argument("ticket")
    w.add_argument("--work-root", default="work")
    w.add_argument("--json", action="store_true")
    w.set_defaults(func=_cmd_work_show)
    w = work_sub.add_parser("validate")
    w.add_argument("--work-root", default="work")
    w.add_argument("--schemas", default="schemas")
    w.set_defaults(func=_cmd_work_validate)
    w = work_sub.add_parser("transition")
    w.add_argument("ticket")
    w.add_argument("status", choices=["active", "implemented", "validated", "closed", "blocked", "superseded"])
    w.add_argument("--work-root", default="work")
    w.add_argument("--validation-report")
    w.add_argument("--regression-report")
    w.add_argument("--reviewed-by")
    w.add_argument("--review-summary")
    w.add_argument("--blocked-reason")
    w.add_argument("--superseded-by")
    w.set_defaults(func=_cmd_work_transition)

    p = sub.add_parser("dev")
    dev_sub = p.add_subparsers(dest="dev_command", required=True)
    d = dev_sub.add_parser("context")
    d.add_argument("--ticket", required=True)
    d.add_argument("--repo-root", default=".")
    d.add_argument("--config")
    d.add_argument("--output")
    d.set_defaults(func=_cmd_dev_context)
    d = dev_sub.add_parser("plan")
    d.add_argument("--ticket", required=True)
    d.add_argument("--repo-root", default=".")
    d.add_argument("--config")
    d.set_defaults(func=_cmd_dev_plan)
    d = dev_sub.add_parser("propose")
    d.add_argument("--ticket", required=True)
    d.add_argument("--backend", default="human")
    d.add_argument("--repo-root", default=".")
    d.set_defaults(func=_cmd_dev_propose)
    d = dev_sub.add_parser("loop")
    d.add_argument("--ticket", required=True)
    d.add_argument("--backend", default="manual")
    d.add_argument("--instruction")
    d.add_argument("--repo-root", default=".")
    d.add_argument("--dry-run", action="store_true")
    d.add_argument("--run-backend", action="store_true")
    d.add_argument("--output")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=_cmd_dev_loop)

    p = sub.add_parser("release")
    release_sub = p.add_subparsers(dest="release_command", required=True)
    r = release_sub.add_parser("check")
    r.add_argument("--ticket")
    r.add_argument("--repo-root", default=".")
    r.add_argument("--validation-report")
    r.add_argument("--skip-tests", action="store_true")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=_cmd_release_check)
    r = release_sub.add_parser("candidate")
    r.add_argument("--ticket", required=True)
    r.add_argument("--repo-root", default=".")
    r.add_argument("--target-version", default="0.2.0")
    r.add_argument("--output")
    r.set_defaults(func=_cmd_release_candidate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser("pga")
    args = parser.parse_args(argv)
    return int(args.func(args))


def artemis_main(argv: list[str] | None = None) -> int:
    parser = build_artemis_parser("artemis")
    args = parser.parse_args(argv)
    return int(args.func(args))
