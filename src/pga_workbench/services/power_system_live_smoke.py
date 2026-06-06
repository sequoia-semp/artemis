from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from jsonschema import Draft202012Validator

from ..data.contracts import DataRequest, DataResult
from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from .fundamentals import load_pjm_fundamental_feeds
from .generation_mix import load_power_generation_mix_feeds
from .power_prices import load_power_system_price_feeds
from .power_system_preflight import (
    DEFAULT_PJM_LOAD_FEEDS,
    DEFAULT_PJM_PRICE_FEEDS,
    build_pjm_ingestion_preflight_report,
    selected_pjm_data_miner_metadata_feeds,
)
from .power_system_source_metadata import (
    select_pjm_data_miner_metadata_expectations,
    verify_pjm_data_miner_definitions,
)
from .source_query_plans import (
    build_pjm_generation_mix_query_requests,
    build_pjm_hourly_lmp_query_requests,
    build_pjm_load_query_requests,
    summarize_source_query_requests,
)

POWER_SYSTEM_LIVE_SMOKE_ERROR = "POWER_SYSTEM_LIVE_SMOKE_ERROR"


class PjmSmokeConnector(Protocol):
    account_class: str

    def available(self) -> bool:
        ...

    def fetch_definition(self, feed: str) -> dict[str, Any]:
        ...

    def fetch(self, request: DataRequest) -> DataResult:
        ...


def build_pjm_live_smoke_report(
    registry_dir: Path,
    connector: PjmSmokeConnector,
    *,
    start: str | None = None,
    end: str | None = None,
    pnode_ids: list[int] | None = None,
    load_feeds: list[str] | None = None,
    price_feeds: list[str] | None = None,
    include_generation_mix: bool = True,
    fetch_source_rows: bool = True,
    row_count: int = 1,
) -> dict[str, Any]:
    registry_dir = Path(registry_dir)
    selected_load_feeds = load_feeds or DEFAULT_PJM_LOAD_FEEDS
    selected_price_feeds = price_feeds or DEFAULT_PJM_PRICE_FEEDS
    selected_pnodes = sorted(set(pnode_ids or []))
    if row_count < 1:
        raise WorkbenchException(POWER_SYSTEM_LIVE_SMOKE_ERROR, "PJM live smoke row_count must be positive")

    preflight = build_pjm_ingestion_preflight_report(
        registry_dir,
        api_key_configured=connector.available(),
        start=start,
        end=end,
        pnode_count=len(selected_pnodes),
        account_class=connector.account_class,
        load_feeds=selected_load_feeds,
        price_feeds=selected_price_feeds,
        include_generation_mix=include_generation_mix,
    )
    metadata = _verify_selected_metadata(
        registry_dir,
        connector,
        selected_load_feeds=selected_load_feeds,
        selected_price_feeds=selected_price_feeds,
        include_generation_mix=include_generation_mix,
    )
    source_fetches: list[dict[str, Any]] = []
    query_execution: dict[str, Any] | None = None
    blockers = list(preflight.get("blockers") or [])
    if fetch_source_rows and preflight.get("ready") is True:
        source_fetches, query_execution = _fetch_source_smoke_rows(
            registry_dir,
            connector,
            start=str(start),
            end=str(end),
            pnode_id=selected_pnodes[0],
            load_feed_id=selected_load_feeds[0],
            price_feed_id=selected_price_feeds[0],
            include_generation_mix=include_generation_mix,
            row_count=row_count,
        )
        errors = [item for item in source_fetches if item.get("status") == "error"]
        if errors:
            blockers.append(
                "PJM live smoke source fetch failed for: "
                + ", ".join(f"{item['data_miner_feed']} ({item.get('error_code')})" for item in errors)
            )
        empty = [item["data_miner_feed"] for item in source_fetches if item.get("status") != "error" and item["row_count"] < 1]
        if empty:
            blockers.append(f"PJM live smoke returned no rows for: {', '.join(empty)}")

    return {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "ready": not blockers,
        "blockers": blockers,
        "preflight": _preflight_evidence(preflight),
        "metadata_verification": _metadata_evidence(metadata),
        "source_fetches": source_fetches,
        "query_execution": query_execution,
        "fetch_source_rows": bool(fetch_source_rows),
        "contains_secret_values": False,
    }


def validate_power_system_source_readiness_report(report: dict[str, Any], schema_dir: Path) -> None:
    schema = load_yaml_unique(Path(schema_dir) / "power_system_source_readiness.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(report), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.path)
        suffix = f" at {path}" if path else ""
        raise WorkbenchException(POWER_SYSTEM_LIVE_SMOKE_ERROR, f"Power-system source readiness report schema violation{suffix}: {first.message}")


def _verify_selected_metadata(
    registry_dir: Path,
    connector: PjmSmokeConnector,
    *,
    selected_load_feeds: list[str],
    selected_price_feeds: list[str],
    include_generation_mix: bool,
) -> dict[str, Any]:
    metadata_feeds = selected_pjm_data_miner_metadata_feeds(
        registry_dir,
        selected_load_feeds,
        selected_price_feeds,
        include_generation_mix,
    )
    definitions = {feed: connector.fetch_definition(feed) for feed in metadata_feeds}
    report = verify_pjm_data_miner_definitions(
        definitions,
        registry_dir,
        feeds=metadata_feeds,
        include_candidate=True,
    )
    report["definition_source"] = "live_pjm_data_miner_definition"
    return report


def _fetch_source_smoke_rows(
    registry_dir: Path,
    connector: PjmSmokeConnector,
    *,
    start: str,
    end: str,
    pnode_id: int,
    load_feed_id: str,
    price_feed_id: str,
    include_generation_mix: bool,
    row_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    fetches = []
    fetches.append(_fetch_one_load_row(registry_dir, connector, load_feed_id, start, end, row_count))
    query_execution = _fetch_pjm_lmp_smoke_rows(
        registry_dir,
        connector,
        price_feed_id=price_feed_id,
        start=start,
        end=end,
        pnode_id=pnode_id,
        row_count=row_count,
        fetches=fetches,
    )
    if include_generation_mix:
        fetches.append(_fetch_one_generation_mix_row(registry_dir, connector, start, end, row_count))
    return fetches, query_execution


def _fetch_one_load_row(
    registry_dir: Path,
    connector: PjmSmokeConnector,
    feed_id: str,
    start: str,
    end: str,
    row_count: int,
) -> dict[str, Any]:
    feed = load_pjm_fundamental_feeds(registry_dir)[feed_id]
    data_miner_feed = str(feed["data_miner_feed"])
    _plan, requests = build_pjm_load_query_requests(
        registry_dir,
        start,
        end,
        [feed_id],
        area=None,
        row_count=row_count,
        account_class=connector.account_class,
        paginate=False,
        max_pages=1,
    )
    request_record = requests[0]
    return _fetch_with_evidence(
        connector,
        product_family="load",
        registry_feed_id=feed_id,
        data_miner_feed=data_miner_feed,
        request=DataRequest(
            contract=feed_id,
            parameters={
                "feed": data_miner_feed,
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
            },
        ),
    )


def _fetch_pjm_lmp_smoke_rows(
    registry_dir: Path,
    connector: PjmSmokeConnector,
    *,
    price_feed_id: str,
    start: str,
    end: str,
    pnode_id: int,
    row_count: int,
    fetches: list[dict[str, Any]],
) -> dict[str, Any]:
    plan, requests = build_pjm_hourly_lmp_query_requests(
        registry_dir,
        start,
        end,
        [price_feed_id],
        [pnode_id],
        row_count=row_count,
        account_class=connector.account_class,
        paginate=False,
        max_pages=1,
    )
    query_execution = summarize_source_query_requests(plan, requests)
    for request_record in requests:
        request = DataRequest(
            contract=request_record.registry_feed_id,
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
                "query_execution_summary": query_execution,
            },
        )
        fetches.append(
            _fetch_with_evidence(
                connector,
                product_family="location" if request_record.request_kind == "metadata" else "price",
                registry_feed_id=request_record.registry_feed_id,
                data_miner_feed=request_record.data_miner_feed,
                request=request,
            )
        )
    return query_execution


def _fetch_one_pnode_row(registry_dir: Path, connector: PjmSmokeConnector, pnode_id: int, row_count: int) -> dict[str, Any]:
    feed = load_power_system_price_feeds(registry_dir)["PJM_PNODE"]
    data_miner_feed = str(feed["data_miner_feed"])
    return _fetch_with_evidence(
        connector,
        product_family="location",
        registry_feed_id="PJM_PNODE",
        data_miner_feed=data_miner_feed,
        request=DataRequest(
            contract="PJM_PNODE",
            parameters={
                "feed": data_miner_feed,
                "query": {
                    "rowCount": row_count,
                    "startRow": 1,
                    "sort": "pnode_id",
                    "order": "Asc",
                    "pnode_id": pnode_id,
                    "fields": _fields_for(registry_dir, data_miner_feed),
                },
                "paginate": False,
                "max_pages": 1,
            },
        ),
    )


def _fetch_one_price_row(
    registry_dir: Path,
    connector: PjmSmokeConnector,
    feed_id: str,
    start: str,
    end: str,
    pnode_id: int,
    row_count: int,
) -> dict[str, Any]:
    feed = load_power_system_price_feeds(registry_dir)[feed_id]
    data_miner_feed = str(feed["data_miner_feed"])
    time_columns = dict(feed["time_columns"])
    start_column = str(time_columns["delivery_start_utc"])
    sort_column = str(time_columns.get("delivery_start_ept") or start_column)
    query: dict[str, Any] = {
        "rowCount": row_count,
        "startRow": 1,
        "sort": sort_column,
        "order": "Asc",
        start_column: _dataminer_date_range(start, end),
        "pnode_id": pnode_id,
        "fields": _fields_for(registry_dir, data_miner_feed),
    }
    for key, value in dict(feed.get("required_filters") or {}).items():
        query[str(key)] = value
    return _fetch_with_evidence(
        connector,
        product_family="price",
        registry_feed_id=feed_id,
        data_miner_feed=data_miner_feed,
        request=DataRequest(
            contract=feed_id,
            parameters={"feed": data_miner_feed, "query": query, "paginate": False, "max_pages": 1},
        ),
    )


def _fetch_one_generation_mix_row(
    registry_dir: Path,
    connector: PjmSmokeConnector,
    start: str,
    end: str,
    row_count: int,
) -> dict[str, Any]:
    feed_id = "PJM_GEN_BY_FUEL"
    data_miner_feed = str(load_power_generation_mix_feeds(registry_dir)[feed_id]["data_miner_feed"])
    _plan, requests = build_pjm_generation_mix_query_requests(
        registry_dir,
        start,
        end,
        row_count=row_count,
        account_class=connector.account_class,
        paginate=False,
        max_pages=1,
    )
    request_record = requests[0]
    return _fetch_with_evidence(
        connector,
        product_family="generation_mix",
        registry_feed_id=feed_id,
        data_miner_feed=data_miner_feed,
        request=DataRequest(
            contract=feed_id,
            parameters={
                "feed": data_miner_feed,
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
            },
        ),
    )


def _fields_for(registry_dir: Path, data_miner_feed: str) -> str:
    expectations = select_pjm_data_miner_metadata_expectations(
        registry_dir,
        feeds=[data_miner_feed],
        include_candidate=True,
    )
    return ",".join(expectations[data_miner_feed].required_fields)


def _fetch_evidence(product_family: str, registry_feed_id: str, data_miner_feed: str, result: DataResult) -> dict[str, Any]:
    lineage = dict(result.lineage or {})
    return {
        "status": "success" if result.records else "empty",
        "product_family": product_family,
        "registry_feed_id": registry_feed_id,
        "data_miner_feed": data_miner_feed,
        "row_count": len(result.records),
        "page_count": int(lineage.get("page_count") or 0),
        "truncated_by_max_pages": bool(lineage.get("truncated_by_max_pages")),
    }


def _fetch_with_evidence(
    connector: PjmSmokeConnector,
    *,
    product_family: str,
    registry_feed_id: str,
    data_miner_feed: str,
    request: DataRequest,
) -> dict[str, Any]:
    try:
        result = connector.fetch(request)
    except WorkbenchException as exc:
        return _fetch_error_evidence(product_family, registry_feed_id, data_miner_feed, exc.code, exc.message)
    except TimeoutError as exc:
        return _fetch_error_evidence(product_family, registry_feed_id, data_miner_feed, "TIMEOUT", str(exc) or "source request timed out")
    except OSError as exc:
        return _fetch_error_evidence(product_family, registry_feed_id, data_miner_feed, exc.__class__.__name__, str(exc))
    return _fetch_evidence(product_family, registry_feed_id, data_miner_feed, result)


def _fetch_error_evidence(
    product_family: str,
    registry_feed_id: str,
    data_miner_feed: str,
    error_code: str,
    error_message: str,
) -> dict[str, Any]:
    return {
        "status": "error",
        "product_family": product_family,
        "registry_feed_id": registry_feed_id,
        "data_miner_feed": data_miner_feed,
        "row_count": 0,
        "page_count": 0,
        "truncated_by_max_pages": False,
        "error_code": error_code,
        "error_message": error_message,
    }


def _preflight_evidence(report: dict[str, Any]) -> dict[str, Any]:
    credential_checks = dict(report.get("credential_checks") or {})
    return {
        "ready": bool(report.get("ready")),
        "blocker_count": len(report.get("blockers") or []),
        "selected_feeds": dict(report.get("selected_feeds") or {}),
        "credential_checks": {
            key: {
                "configured": bool(value.get("configured")) if isinstance(value, dict) else False,
                "value_redacted": True,
            }
            for key, value in credential_checks.items()
        },
        "contains_secret_values": False,
    }


def _metadata_evidence(report: dict[str, Any]) -> dict[str, Any]:
    verified_feeds = []
    for item in report.get("verified_feeds") or []:
        verified_feeds.append(
            {
                "registry_feed_id": item.get("registry_feed_id"),
                "data_miner_feed": item.get("data_miner_feed"),
                "required_field_count": int(item.get("required_field_count") or 0),
                "observed_field_count": int(item.get("observed_field_count") or 0),
            }
        )
    return {
        "definition_source": report.get("definition_source"),
        "verified_feed_count": int(report.get("verified_feed_count") or len(verified_feeds)),
        "verified_feeds": verified_feeds,
        "contains_secret_values": False,
    }


def _dataminer_date_range(start: str, end: str) -> str:
    return f"{start} 00:00:00 to {end} 23:59:59"
