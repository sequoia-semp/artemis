from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from .fundamentals import load_pjm_fundamental_feeds
from .power_system_retention import load_power_system_artifact_retention_policies, validate_power_system_artifact_retention_references
from .source_query_plans import (
    SourceQueryPlan,
    SourceQueryRequest,
    build_pjm_generation_mix_query_requests,
    build_pjm_hourly_lmp_query_requests,
    build_pjm_load_query_requests,
)

HISTORICAL_SOURCE_ROUTER_ERROR = "HISTORICAL_SOURCE_ROUTER_ERROR"


def build_historical_source_request_plan(
    registry_dir: Path,
    artifact_key: str,
    *,
    as_of: str,
    pnode_ids: list[int] | None = None,
    price_feed_ids: list[str] | None = None,
    load_feed_ids: list[str] | None = None,
    row_count: int = 50000,
    account_class: str = "non_member",
    paginate: bool = True,
    max_pages: int = 1,
) -> dict[str, Any]:
    registry_dir = Path(registry_dir)
    validate_power_system_artifact_retention_references(registry_dir)
    policies = load_power_system_artifact_retention_policies(registry_dir)
    policy = policies.get(artifact_key)
    if not isinstance(policy, dict):
        raise WorkbenchException(HISTORICAL_SOURCE_ROUTER_ERROR, f"Unknown historical source artifact key: {artifact_key}")
    historical = dict(policy.get("historical_source_policy") or {})
    if historical.get("source_restorable") is not True:
        raise WorkbenchException(HISTORICAL_SOURCE_ROUTER_ERROR, f"{artifact_key} is not source-restorable")
    history_start, history_end = _history_window(as_of, historical)

    plans: list[SourceQueryPlan] = []
    requests: list[SourceQueryRequest] = []
    if artifact_key == "pjm_power_prices":
        if not pnode_ids:
            raise WorkbenchException(HISTORICAL_SOURCE_ROUTER_ERROR, "pjm_power_prices historical requests require pnode_ids")
        plan, built = build_pjm_hourly_lmp_query_requests(
            registry_dir,
            history_start,
            history_end,
            price_feed_ids or ["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"],
            pnode_ids,
            row_count=row_count,
            account_class=account_class,
            paginate=paginate,
            max_pages=max_pages,
        )
        plans.append(plan)
        requests.extend(built)
    elif artifact_key == "pjm_load_fundamentals":
        plan, built = build_pjm_load_query_requests(
            registry_dir,
            history_start,
            history_end,
            load_feed_ids or _default_approved_pjm_load_feeds(registry_dir),
            area=None,
            row_count=row_count,
            account_class=account_class,
            paginate=paginate,
            max_pages=max_pages,
        )
        plans.append(plan)
        requests.extend(built)
    elif artifact_key == "pjm_generation_mix":
        plan, built = build_pjm_generation_mix_query_requests(
            registry_dir,
            history_start,
            history_end,
            row_count=row_count,
            account_class=account_class,
            paginate=paginate,
            max_pages=max_pages,
        )
        plans.append(plan)
        requests.extend(built)
    else:
        raise WorkbenchException(HISTORICAL_SOURCE_ROUTER_ERROR, f"No historical source router is implemented for {artifact_key}")

    return {
        "artifact_key": artifact_key,
        "operator_id": policy.get("operator_id"),
        "product_family": policy.get("product_family"),
        "as_of": _as_of_day(as_of).isoformat(),
        "history_start": history_start,
        "history_end": history_end,
        "derived_view_windows_days": [int(item) for item in historical.get("derived_view_windows_days") or []],
        "approved_query_plan_ids": list(historical.get("approved_query_plan_ids") or []),
        "row_version_policy": historical.get("row_version_policy"),
        "request_count": len(requests),
        "query_plans": [_plan_summary(plan) for plan in plans],
        "requests": [_request_summary(request) for request in requests],
        "contains_secret_values": False,
    }


def _history_window(as_of: str, historical: dict[str, Any]) -> tuple[str, str]:
    as_of_day = _as_of_day(as_of)
    windows = [int(item) for item in historical.get("derived_view_windows_days") or []]
    max_window = max(windows or [0])
    max_hot = historical.get("max_hot_history_days")
    if max_hot is not None:
        max_window = min(max_window, int(max_hot))
    return (as_of_day - timedelta(days=max_window)).isoformat(), as_of_day.isoformat()


def _as_of_day(value: str) -> date:
    raw = str(value).strip()
    if len(raw) == 10:
        return date.fromisoformat(raw)
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise WorkbenchException(HISTORICAL_SOURCE_ROUTER_ERROR, f"as_of is not a recognized timestamp: {value}") from exc
    return parsed.date()


def _default_approved_pjm_load_feeds(registry_dir: Path) -> list[str]:
    feeds = load_pjm_fundamental_feeds(registry_dir)
    selected = [
        feed_id
        for feed_id, feed in sorted(feeds.items())
        if feed.get("status") == "approved_core" and feed.get("source_contract") == "iso_load"
    ]
    if not selected:
        raise WorkbenchException(HISTORICAL_SOURCE_ROUTER_ERROR, "No approved PJM load feeds are available for historical routing")
    return selected


def _plan_summary(plan: SourceQueryPlan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "planned_request_count": plan.planned_request_count,
        "max_connections_per_minute": plan.max_connections_per_minute,
        "account_class": plan.account_class,
        "windows": [{"start": window.start, "end": window.end} for window in plan.windows],
        "lineage": plan.lineage,
    }


def _request_summary(request: SourceQueryRequest) -> dict[str, Any]:
    return {
        "request_id": request.request_id,
        "request_kind": request.request_kind,
        "registry_feed_id": request.registry_feed_id,
        "data_miner_feed": request.data_miner_feed,
        "pnode_id": request.pnode_id,
        "window_start": request.window_start,
        "window_end": request.window_end,
        "paginate": request.paginate,
        "max_pages": request.max_pages,
        "query_parameter_keys": sorted(str(key) for key in request.query),
    }
