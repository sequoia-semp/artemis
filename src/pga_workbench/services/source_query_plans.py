from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from .power_system_sources import load_known_power_feed_ids, load_power_system_source_catalog
from .source_access_policies import load_power_system_source_access_policies

SOURCE_QUERY_PLAN_ERROR = "SOURCE_QUERY_PLAN_ERROR"


@dataclass(frozen=True)
class QueryDateWindow:
    start: str
    end: str


@dataclass(frozen=True)
class SourceQueryPlan:
    plan_id: str
    windows: list[QueryDateWindow]
    planned_request_count: int
    max_connections_per_minute: int
    account_class: str
    lineage: dict[str, Any]


@dataclass(frozen=True)
class SourceQueryRequest:
    request_id: str
    request_kind: str
    registry_feed_id: str
    data_miner_feed: str
    pnode_id: int | None
    window_start: str | None
    window_end: str | None
    query: dict[str, Any]
    paginate: bool
    max_pages: int
    query_plan: dict[str, Any]


def load_power_system_source_query_plans(registry_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_yaml_unique(Path(registry_dir) / "power_system_source_query_plans.yaml")
    if not isinstance(data, dict):
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, "Power system source query plans must be a mapping")
    return {str(key): dict(value) for key, value in data.items() if isinstance(value, dict)}


def validate_power_system_source_query_plan_references(registry_dir: Path) -> dict[str, dict[str, Any]]:
    plans = load_power_system_source_query_plans(registry_dir)
    catalog = load_power_system_source_catalog(registry_dir)
    known_feed_ids = load_known_power_feed_ids(registry_dir)
    feed_publications: dict[str, list[str]] = {}
    for publication_id, publication in catalog.items():
        for feed_id in publication.get("registry_feed_ids") or []:
            feed_publications.setdefault(str(feed_id), []).append(str(publication_id))
    resolved: dict[str, dict[str, Any]] = {}
    for plan_id, record in plans.items():
        publication_id = str(record.get("publication_id") or "")
        publication = catalog.get(publication_id)
        if not isinstance(publication, dict):
            raise WorkbenchException(
                SOURCE_QUERY_PLAN_ERROR,
                f"Source query plan {plan_id} references unknown source publication: {publication_id}",
            )
        if record.get("status") == "approved_core" and publication.get("status") != "approved_core":
            raise WorkbenchException(
                SOURCE_QUERY_PLAN_ERROR,
                f"Approved source query plan {plan_id} references non-approved source publication: {publication_id}",
            )
        feed_ids = [str(item) for item in record.get("applies_to_feed_ids") or []]
        missing = [feed_id for feed_id in feed_ids if feed_id not in known_feed_ids]
        if missing:
            raise WorkbenchException(
                SOURCE_QUERY_PLAN_ERROR,
                f"Source query plan {plan_id} references unknown feed descriptors: {', '.join(missing)}",
            )
        unpublished = [feed_id for feed_id in feed_ids if not feed_publications.get(feed_id)]
        if unpublished:
            raise WorkbenchException(
                SOURCE_QUERY_PLAN_ERROR,
                f"Source query plan {plan_id} applies to feeds without source publication coverage: {', '.join(unpublished)}",
            )
        resolved[plan_id] = {
            "publication_id": publication_id,
            "feed_ids": feed_ids,
            "feed_publications": {feed_id: feed_publications.get(feed_id, []) for feed_id in feed_ids},
        }
    return resolved


def _parse_day(value: str, label: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"{label} must be YYYY-MM-DD: {value}") from exc


def _day_windows(start: str, end: str, max_days_per_request: int) -> list[QueryDateWindow]:
    start_day = _parse_day(start, "start")
    end_day = _parse_day(end, "end")
    if end_day < start_day:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, "end must be on or after start")
    windows: list[QueryDateWindow] = []
    cursor = start_day
    step = timedelta(days=max_days_per_request - 1)
    while cursor <= end_day:
        window_end = min(cursor + step, end_day)
        windows.append(QueryDateWindow(start=cursor.isoformat(), end=window_end.isoformat()))
        cursor = window_end + timedelta(days=1)
    return windows


def _account_connection_limit(access_policy: dict[str, Any], account_class: str) -> int:
    account_classes = dict(access_policy.get("account_classes") or {})
    record = account_classes.get(account_class)
    if not isinstance(record, dict):
        allowed = ", ".join(sorted(account_classes))
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"Unknown account class {account_class!r}; expected one of {allowed}")
    return int(record["max_connections_per_minute"])


def plan_pjm_hourly_lmp_queries(
    registry_dir: Path,
    start: str,
    end: str,
    feed_ids: list[str],
    pnode_count: int,
    account_class: str = "non_member",
) -> SourceQueryPlan:
    plans = load_power_system_source_query_plans(registry_dir)
    plan_id = "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS"
    record = plans.get(plan_id)
    if not isinstance(record, dict) or record.get("status") != "approved_core":
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"Missing approved source query plan: {plan_id}")
    allowed_feed_ids = set(record["applies_to_feed_ids"])
    unsupported = sorted(set(feed_ids) - allowed_feed_ids)
    if unsupported:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"Unsupported feed for {plan_id}: {', '.join(unsupported)}")
    if pnode_count < 1:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, "At least one pnode is required for PJM hourly LMP query planning")

    date_window = dict(record["date_window"])
    windows = _day_windows(start, end, int(date_window["max_days_per_request"]))
    budget = dict(record["planned_request_budget"])
    metadata_requests = int(budget["metadata_requests_per_pnode"])
    planned_request_count = pnode_count * (metadata_requests + (len(feed_ids) * len(windows)))

    access_policy_id = str(record["access_policy_id"])
    access_policy = load_power_system_source_access_policies(registry_dir).get(access_policy_id)
    if not isinstance(access_policy, dict):
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"Missing source access policy: {access_policy_id}")
    max_connections = _account_connection_limit(access_policy, account_class)
    if budget.get("enforce_account_class_budget") and planned_request_count > max_connections:
        raise WorkbenchException(
            SOURCE_QUERY_PLAN_ERROR,
            f"PJM hourly LMP plan requires {planned_request_count} requests but {account_class} budget is {max_connections} per minute",
        )

    return SourceQueryPlan(
        plan_id=plan_id,
        windows=windows,
        planned_request_count=planned_request_count,
        max_connections_per_minute=max_connections,
        account_class=account_class,
        lineage={
            "plan_id": plan_id,
            "publication_id": record["publication_id"],
            "access_policy_id": access_policy_id,
            "feed_ids": list(feed_ids),
            "pnode_count": pnode_count,
            "metadata_requests_per_pnode": metadata_requests,
            "date_window_count": len(windows),
            "max_days_per_request": int(date_window["max_days_per_request"]),
        },
    )


def build_pjm_hourly_lmp_query_requests(
    registry_dir: Path,
    start: str,
    end: str,
    feed_ids: list[str],
    pnode_ids: list[int],
    *,
    row_count: int,
    account_class: str = "non_member",
    paginate: bool = True,
    max_pages: int = 1,
) -> tuple[SourceQueryPlan, list[SourceQueryRequest]]:
    if row_count < 1:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, "row_count must be positive for query request planning")
    if max_pages < 1:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, "max_pages must be positive for query request planning")
    unique_pnodes = sorted(set(int(item) for item in pnode_ids))
    plan = plan_pjm_hourly_lmp_queries(
        registry_dir,
        start,
        end,
        feed_ids,
        pnode_count=len(unique_pnodes),
        account_class=account_class,
    )
    price_feeds = _load_price_feeds(registry_dir)
    requests: list[SourceQueryRequest] = []
    for pnode_id in unique_pnodes:
        requests.append(
            SourceQueryRequest(
                request_id=f"{plan.plan_id}.PNODE.{pnode_id}",
                request_kind="metadata",
                registry_feed_id="PJM_PNODE",
                data_miner_feed="pnode",
                pnode_id=pnode_id,
                window_start=None,
                window_end=None,
                query=_pnode_query(pnode_id, row_count),
                paginate=False,
                max_pages=1,
                query_plan=plan.lineage,
            )
        )
        for feed_id in feed_ids:
            feed = price_feeds.get(feed_id)
            if not isinstance(feed, dict):
                raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"Missing price feed descriptor for query planning: {feed_id}")
            for window in plan.windows:
                requests.append(
                    SourceQueryRequest(
                        request_id=f"{plan.plan_id}.{feed_id}.{pnode_id}.{window.start}",
                        request_kind="source_rows",
                        registry_feed_id=feed_id,
                        data_miner_feed=str(feed["data_miner_feed"]),
                        pnode_id=pnode_id,
                        window_start=window.start,
                        window_end=window.end,
                        query=_lmp_query(feed, window.start, window.end, pnode_id, row_count),
                        paginate=bool(paginate),
                        max_pages=int(max_pages),
                        query_plan=plan.lineage,
                    )
                )
    if len(requests) != plan.planned_request_count:
        raise WorkbenchException(
            SOURCE_QUERY_PLAN_ERROR,
            f"Planned request count mismatch: planned {plan.planned_request_count}, built {len(requests)}",
        )
    return plan, requests


def build_pjm_load_query_requests(
    registry_dir: Path,
    start: str,
    end: str,
    feed_ids: list[str],
    *,
    area: str | None,
    row_count: int,
    account_class: str = "non_member",
    paginate: bool = True,
    max_pages: int = 1,
) -> tuple[SourceQueryPlan, list[SourceQueryRequest]]:
    _validate_bounded_request_inputs(registry_dir, row_count=row_count, max_pages=max_pages)
    feeds = _load_fundamental_feeds(registry_dir)
    plan = _bounded_interval_plan(
        registry_dir,
        plan_id="PJM_DATAMINER_LOAD_BOUNDED_INTERVAL",
        feed_ids=feed_ids,
        start=start,
        end=end,
        account_class=account_class,
    )
    requests: list[SourceQueryRequest] = []
    for feed_id in feed_ids:
        feed = feeds.get(feed_id)
        if not isinstance(feed, dict):
            raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"Missing PJM load feed descriptor for query planning: {feed_id}")
        requests.append(
            SourceQueryRequest(
                request_id=f"{plan.plan_id}.{feed_id}.{start}.{end}",
                request_kind="source_rows",
                registry_feed_id=feed_id,
                data_miner_feed=str(feed["data_miner_feed"]),
                pnode_id=None,
                window_start=start,
                window_end=end,
                query=_load_query(feed, start, end, area, row_count),
                paginate=bool(paginate),
                max_pages=int(max_pages),
                query_plan=plan.lineage,
            )
        )
    _require_request_count_match(plan, requests)
    return plan, requests


def build_pjm_generation_mix_query_requests(
    registry_dir: Path,
    start: str,
    end: str,
    *,
    row_count: int,
    account_class: str = "non_member",
    paginate: bool = True,
    max_pages: int = 1,
) -> tuple[SourceQueryPlan, list[SourceQueryRequest]]:
    _validate_bounded_request_inputs(registry_dir, row_count=row_count, max_pages=max_pages)
    feeds = _load_generation_mix_feeds(registry_dir)
    feed_id = "PJM_GEN_BY_FUEL"
    feed = feeds.get(feed_id)
    if not isinstance(feed, dict):
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"Missing PJM generation mix feed descriptor for query planning: {feed_id}")
    plan = _bounded_interval_plan(
        registry_dir,
        plan_id="PJM_DATAMINER_GENERATION_MIX_BOUNDED_INTERVAL",
        feed_ids=[feed_id],
        start=start,
        end=end,
        account_class=account_class,
    )
    requests = [
        SourceQueryRequest(
            request_id=f"{plan.plan_id}.{feed_id}.{start}.{end}",
            request_kind="source_rows",
            registry_feed_id=feed_id,
            data_miner_feed=str(feed["data_miner_feed"]),
            pnode_id=None,
            window_start=start,
            window_end=end,
            query=_generation_mix_query(feed, start, end, row_count),
            paginate=bool(paginate),
            max_pages=int(max_pages),
            query_plan=plan.lineage,
        )
    ]
    _require_request_count_match(plan, requests)
    return plan, requests


def summarize_source_query_requests(plan: SourceQueryPlan, requests: list[SourceQueryRequest]) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "planned_request_count": plan.planned_request_count,
        "built_request_count": len(requests),
        "account_class": plan.account_class,
        "max_connections_per_minute": plan.max_connections_per_minute,
        "request_kinds": {
            kind: sum(1 for item in requests if item.request_kind == kind)
            for kind in sorted({item.request_kind for item in requests})
        },
        "registry_feed_ids": sorted({item.registry_feed_id for item in requests}),
        "pnode_ids": sorted({item.pnode_id for item in requests if item.pnode_id is not None}),
        "date_windows": [dict(start=item.start, end=item.end) for item in plan.windows],
        "contains_secret_values": False,
    }


def _bounded_interval_plan(
    registry_dir: Path,
    *,
    plan_id: str,
    feed_ids: list[str],
    start: str,
    end: str,
    account_class: str,
) -> SourceQueryPlan:
    plans = load_power_system_source_query_plans(registry_dir)
    record = plans.get(plan_id)
    if not isinstance(record, dict) or record.get("status") != "approved_core":
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"Missing approved source query plan: {plan_id}")
    allowed_feed_ids = set(record["applies_to_feed_ids"])
    unsupported = sorted(set(feed_ids) - allowed_feed_ids)
    if unsupported:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"Unsupported feed for {plan_id}: {', '.join(unsupported)}")
    if not feed_ids:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"{plan_id} requires at least one feed")
    date_window = dict(record["date_window"])
    if date_window.get("mode") != "bounded_interval":
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"{plan_id} must use bounded_interval date windows")
    windows = _day_windows(start, end, int(date_window["max_days_per_request"]))
    if len(windows) != 1:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"{plan_id} expected one bounded interval window")
    access_policy_id = str(record["access_policy_id"])
    access_policy = load_power_system_source_access_policies(registry_dir).get(access_policy_id)
    if not isinstance(access_policy, dict):
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"Missing source access policy: {access_policy_id}")
    max_connections = _account_connection_limit(access_policy, account_class)
    planned_request_count = len(feed_ids)
    budget = dict(record["planned_request_budget"])
    if budget.get("enforce_account_class_budget") and planned_request_count > max_connections:
        raise WorkbenchException(
            SOURCE_QUERY_PLAN_ERROR,
            f"{plan_id} requires {planned_request_count} requests but {account_class} budget is {max_connections} per minute",
        )
    return SourceQueryPlan(
        plan_id=plan_id,
        windows=windows,
        planned_request_count=planned_request_count,
        max_connections_per_minute=max_connections,
        account_class=account_class,
        lineage={
            "plan_id": plan_id,
            "publication_id": record["publication_id"],
            "access_policy_id": access_policy_id,
            "feed_ids": list(feed_ids),
            "pnode_count": 0,
            "date_window_count": len(windows),
            "max_days_per_request": int(date_window["max_days_per_request"]),
        },
    )


def _validate_bounded_request_inputs(registry_dir: Path, *, row_count: int, max_pages: int) -> None:
    access_policy = load_power_system_source_access_policies(registry_dir).get("PJM_DATAMINER_API_PUBLIC_USE")
    if not isinstance(access_policy, dict):
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, "Missing source access policy: PJM_DATAMINER_API_PUBLIC_USE")
    row_policy = dict(access_policy.get("row_count") or {})
    min_rows = int(row_policy.get("minimum") or 1)
    max_rows = int(row_policy.get("maximum") or 50000)
    if row_count < min_rows or row_count > max_rows:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, f"row_count must be between {min_rows} and {max_rows}")
    pagination = dict(access_policy.get("pagination") or {})
    if max_pages < 1:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, "max_pages must be positive for query request planning")
    if pagination.get("allow_unbounded") is False and max_pages < 1:
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, "unbounded pagination is not allowed")


def _require_request_count_match(plan: SourceQueryPlan, requests: list[SourceQueryRequest]) -> None:
    if len(requests) != plan.planned_request_count:
        raise WorkbenchException(
            SOURCE_QUERY_PLAN_ERROR,
            f"Planned request count mismatch: planned {plan.planned_request_count}, built {len(requests)}",
        )


def _load_price_feeds(registry_dir: Path) -> dict[str, dict[str, Any]]:
    payload = load_yaml_unique(Path(registry_dir) / "power_system_price_feeds.yaml")
    if not isinstance(payload, dict):
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, "power_system_price_feeds.yaml must be a mapping")
    return {str(key): dict(value) for key, value in payload.items() if isinstance(value, dict)}


def _load_fundamental_feeds(registry_dir: Path) -> dict[str, dict[str, Any]]:
    payload = load_yaml_unique(Path(registry_dir) / "pjm_fundamental_feeds.yaml")
    if not isinstance(payload, dict):
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, "pjm_fundamental_feeds.yaml must be a mapping")
    return {str(key): dict(value) for key, value in payload.items() if isinstance(value, dict)}


def _load_generation_mix_feeds(registry_dir: Path) -> dict[str, dict[str, Any]]:
    payload = load_yaml_unique(Path(registry_dir) / "power_generation_mix_feeds.yaml")
    if not isinstance(payload, dict):
        raise WorkbenchException(SOURCE_QUERY_PLAN_ERROR, "power_generation_mix_feeds.yaml must be a mapping")
    return {str(key): dict(value) for key, value in payload.items() if isinstance(value, dict)}


def _dataminer_date_range(start: str, end: str) -> str:
    return f"{start} 00:00:00 to {end} 23:59:59"


def _pnode_query(pnode_id: int, row_count: int) -> dict[str, Any]:
    return {
        "rowCount": row_count,
        "startRow": 1,
        "sort": "pnode_id",
        "order": "Asc",
        "pnode_id": pnode_id,
        "fields": "pnode_id,pnode_name,pnode_type,pnode_subtype,zone,voltage_level,effective_date,termination_date",
    }


def _load_query(feed: dict[str, Any], start: str, end: str, area: str | None, row_count: int) -> dict[str, Any]:
    time_columns = dict(feed["time_columns"])
    start_column = str(time_columns["delivery_start_utc"])
    sort_column = str(time_columns.get("delivery_start_ept") or start_column)
    query: dict[str, Any] = {
        "rowCount": row_count,
        "startRow": 1,
        "sort": sort_column,
        "order": "Asc",
        start_column: _dataminer_date_range(start, end),
    }
    fields = [value for value in time_columns.values() if value]
    fields.extend(feed.get("area_columns") or [])
    fields.extend(feed.get("value_columns") or [])
    query["fields"] = ",".join(dict.fromkeys(str(field) for field in fields))
    area_filter = area or feed.get("default_area_filter")
    area_columns = list(feed.get("area_columns") or [])
    if area_filter and area_columns:
        query[str(area_columns[0])] = area_filter
    return query


def _generation_mix_query(feed: dict[str, Any], start: str, end: str, row_count: int) -> dict[str, Any]:
    time_columns = dict(feed["time_columns"])
    fuel_columns = dict(feed["fuel_columns"])
    value_columns = dict(feed["value_columns"])
    fields = [value for value in time_columns.values() if value]
    fields.extend(value for value in fuel_columns.values() if value)
    fields.extend(value for value in value_columns.values() if value)
    start_column = str(time_columns["delivery_start_utc"])
    return {
        "rowCount": row_count,
        "startRow": 1,
        "sort": start_column,
        "order": "Asc",
        start_column: _dataminer_date_range(start, end),
        "fields": ",".join(dict.fromkeys(str(field) for field in fields if field)),
    }


def _lmp_query(feed: dict[str, Any], start: str, end: str, pnode_id: int, row_count: int) -> dict[str, Any]:
    time_columns = dict(feed["time_columns"])
    pnode_columns = dict(feed["pnode_columns"])
    value_columns = dict(feed.get("value_columns") or {})
    version_columns = dict(feed.get("version_columns") or {})
    start_column = str(time_columns["delivery_start_utc"])
    sort_column = str(time_columns.get("delivery_start_ept") or start_column)
    fields = [value for value in time_columns.values() if value]
    fields.extend(value for value in pnode_columns.values() if value)
    fields.extend(value_columns.values())
    fields.extend(version_columns.values())
    query: dict[str, Any] = {
        "rowCount": row_count,
        "startRow": 1,
        "sort": sort_column,
        "order": "Asc",
        start_column: _dataminer_date_range(start, end),
        "pnode_id": pnode_id,
        "fields": ",".join(dict.fromkeys(str(field) for field in fields if field)),
    }
    for key, value in dict(feed.get("required_filters") or {}).items():
        query[str(key)] = value
    return query
