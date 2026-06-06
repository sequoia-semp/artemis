from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from .fundamentals import load_pjm_fundamental_feeds
from .generation_mix import load_power_generation_mix_feeds
from .power_prices import load_power_system_price_feeds
from .power_system_source_metadata import select_pjm_data_miner_metadata_expectations
from .source_access_policies import source_access_policy_for_surface
from .source_query_plans import build_pjm_generation_mix_query_requests, build_pjm_load_query_requests, plan_pjm_hourly_lmp_queries

POWER_SYSTEM_PREFLIGHT_ERROR = "POWER_SYSTEM_PREFLIGHT_ERROR"

DEFAULT_PJM_LOAD_FEEDS = ["hrl_load_metered", "hrl_load_prelim", "load_frcstd_7_day", "load_frcstd_hist"]
DEFAULT_PJM_PRICE_FEEDS = ["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"]


def build_pjm_ingestion_preflight_report(
    registry_dir: Path,
    *,
    api_key_configured: bool,
    start: str | None = None,
    end: str | None = None,
    pnode_count: int = 0,
    account_class: str = "non_member",
    load_feeds: list[str] | None = None,
    price_feeds: list[str] | None = None,
    include_generation_mix: bool = True,
) -> dict[str, Any]:
    registry_dir = Path(registry_dir)
    selected_load_feeds = load_feeds or DEFAULT_PJM_LOAD_FEEDS
    selected_price_feeds = price_feeds or DEFAULT_PJM_PRICE_FEEDS
    blockers: list[str] = []

    _validate_selected_feeds(registry_dir, selected_load_feeds, selected_price_feeds)
    access_policy = source_access_policy_for_surface(registry_dir, "pjm_data_miner_api")
    account_classes = dict(access_policy.get("account_classes") or {})
    if account_class not in account_classes:
        allowed = ", ".join(sorted(account_classes))
        raise WorkbenchException(POWER_SYSTEM_PREFLIGHT_ERROR, f"Unknown PJM account class {account_class!r}; expected one of {allowed}")
    if not api_key_configured:
        blockers.append("ARTEMIS_PJM_API_KEY is not configured")
    if not start or not end:
        blockers.append("start and end date window is required for live ingestion planning")
    if pnode_count < 1:
        blockers.append("at least one PJM pnode/location is required for live LMP ingestion")

    metadata_feeds = selected_pjm_data_miner_metadata_feeds(registry_dir, selected_load_feeds, selected_price_feeds, include_generation_mix)
    metadata_expectations = select_pjm_data_miner_metadata_expectations(registry_dir, feeds=metadata_feeds, include_candidate=True)

    query_plan: dict[str, Any] | None = None
    query_plans: dict[str, dict[str, Any]] = {}
    if start and end:
        try:
            load_plan, load_requests = build_pjm_load_query_requests(
                registry_dir,
                start,
                end,
                selected_load_feeds,
                area=None,
                row_count=1,
                account_class=account_class,
                paginate=False,
                max_pages=1,
            )
            query_plans["load"] = _query_plan_summary(load_plan, built_request_count=len(load_requests))
        except WorkbenchException as exc:
            blockers.append(f"{exc.code}: {exc.message}")
        if include_generation_mix:
            try:
                generation_plan, generation_requests = build_pjm_generation_mix_query_requests(
                    registry_dir,
                    start,
                    end,
                    row_count=1,
                    account_class=account_class,
                    paginate=False,
                    max_pages=1,
                )
                query_plans["generation_mix"] = _query_plan_summary(generation_plan, built_request_count=len(generation_requests))
            except WorkbenchException as exc:
                blockers.append(f"{exc.code}: {exc.message}")
    if start and end and pnode_count >= 1:
        try:
            plan = plan_pjm_hourly_lmp_queries(
                registry_dir,
                start,
                end,
                selected_price_feeds,
                pnode_count=pnode_count,
                account_class=account_class,
            )
            query_plan = _query_plan_summary(plan)
            query_plans["price"] = query_plan
        except WorkbenchException as exc:
            blockers.append(f"{exc.code}: {exc.message}")

    return {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "ready": not blockers,
        "blockers": blockers,
        "credential_checks": {
            "ARTEMIS_PJM_API_KEY": {
                "configured": bool(api_key_configured),
                "value_redacted": True,
            }
        },
        "selected_feeds": {
            "load": list(selected_load_feeds),
            "price": list(selected_price_feeds),
            "generation_mix": ["PJM_GEN_BY_FUEL"] if include_generation_mix else [],
            "metadata_data_miner_feeds": sorted(metadata_expectations),
        },
        "source_access_policy": {
            "access_surface": access_policy["access_surface"],
            "account_class": account_class,
            "max_connections_per_minute": int(account_classes[account_class]["max_connections_per_minute"]),
            "row_count_maximum": int(access_policy["row_count"]["maximum"]),
            "pagination_allow_unbounded": bool(access_policy["pagination"]["allow_unbounded"]),
        },
        "metadata_expectations": [
            {
                "registry_feed_id": item.registry_feed_id,
                "data_miner_feed": item.data_miner_feed,
                "product_family": item.product_family,
                "required_field_count": len(item.required_fields),
                "status": item.status,
            }
            for item in sorted(metadata_expectations.values(), key=lambda value: value.data_miner_feed)
        ],
        "query_plan": query_plan,
        "query_plans": query_plans,
    }


def _validate_selected_feeds(registry_dir: Path, load_feeds: list[str], price_feeds: list[str]) -> None:
    load_registry = load_pjm_fundamental_feeds(registry_dir)
    price_registry = load_power_system_price_feeds(registry_dir)
    unknown_load = sorted(set(load_feeds) - set(load_registry))
    unknown_price = sorted(set(price_feeds) - set(price_registry))
    if unknown_load:
        raise WorkbenchException(POWER_SYSTEM_PREFLIGHT_ERROR, f"Unknown PJM load feeds: {', '.join(unknown_load)}")
    if unknown_price:
        raise WorkbenchException(POWER_SYSTEM_PREFLIGHT_ERROR, f"Unknown PJM price feeds: {', '.join(unknown_price)}")


def _query_plan_summary(plan: Any, *, built_request_count: int | None = None) -> dict[str, Any]:
    summary = {
        "plan_id": plan.plan_id,
        "planned_request_count": plan.planned_request_count,
        "max_connections_per_minute": plan.max_connections_per_minute,
        "account_class": plan.account_class,
        "windows": [{"start": item.start, "end": item.end} for item in plan.windows],
        "lineage": plan.lineage,
    }
    if built_request_count is not None:
        summary["built_request_count"] = built_request_count
    return summary


def selected_pjm_data_miner_metadata_feeds(
    registry_dir: Path,
    load_feeds: list[str],
    price_feeds: list[str],
    include_generation_mix: bool,
) -> list[str]:
    load_registry = load_pjm_fundamental_feeds(registry_dir)
    price_registry = load_power_system_price_feeds(registry_dir)
    generation_registry = load_power_generation_mix_feeds(registry_dir)
    feeds = [str(load_registry[feed]["data_miner_feed"]) for feed in load_feeds]
    feeds.extend(str(price_registry[feed]["data_miner_feed"]) for feed in price_feeds)
    feeds.append(str(price_registry["PJM_PNODE"]["data_miner_feed"]))
    if include_generation_mix:
        feeds.append(str(generation_registry["PJM_GEN_BY_FUEL"]["data_miner_feed"]))
    return sorted(set(feeds))
