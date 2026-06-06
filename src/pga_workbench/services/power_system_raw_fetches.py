from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..data.contracts import DataResult
from ..exceptions import WorkbenchException
from ..serialization import to_plain

POWER_SYSTEM_RAW_FETCH_ERROR = "POWER_SYSTEM_RAW_FETCH_ERROR"


def build_raw_source_fetch_manifest(
    *,
    operator_id: str,
    source_system: str,
    source_surface: str,
    request_record: Any,
    result: DataResult,
    query_execution_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_execution = dict(query_execution_summary or {})
    query = dict(getattr(request_record, "query", {}) or {})
    plan = dict(getattr(request_record, "query_plan", {}) or {})
    row_count = len(result.records)
    result_lineage = dict(result.lineage or {})
    request_id = str(getattr(request_record, "request_id"))
    return {
        "manifest_id": f"{operator_id}.{source_system}.{request_id}",
        "operator_id": operator_id,
        "source_system": source_system,
        "source_surface": source_surface,
        "source_name": result.source,
        "data_environment": result.data_environment,
        "contract": result.contract,
        "registry_feed_id": str(getattr(request_record, "registry_feed_id")),
        "source_feed": str(getattr(request_record, "data_miner_feed")),
        "request_id": request_id,
        "request_kind": str(getattr(request_record, "request_kind")),
        "query_plan_id": str(query_execution.get("plan_id") or plan.get("plan_id") or ""),
        "window_start": getattr(request_record, "window_start", None),
        "window_end": getattr(request_record, "window_end", None),
        "pnode_id": getattr(request_record, "pnode_id", None),
        "row_count": row_count,
        "total_rows": _optional_int(result_lineage.get("total_rows")),
        "page_count": _optional_int(result_lineage.get("page_count")),
        "max_pages": _optional_int(result_lineage.get("max_pages")),
        "truncated_by_max_pages": bool(result_lineage.get("truncated_by_max_pages")),
        "query_parameter_keys": sorted(str(key) for key in query),
        "query_fields": _query_fields(query.get("fields")),
        "raw_records_sha256": _records_hash(result.records),
        "contains_raw_records": False,
        "contains_secret_values": False,
    }


def validate_raw_source_fetch_manifests(manifests: list[dict[str, Any]], schema_dir: Path) -> None:
    schema = _load_schema(Path(schema_dir))
    errors = []
    for index, manifest in enumerate(manifests):
        for error in Draft202012Validator(schema).iter_errors(manifest):
            errors.append((index, error))
    if errors:
        index, first = sorted(errors, key=lambda item: (item[0], list(item[1].path)))[0]
        path = ".".join(str(part) for part in first.path)
        suffix = f" at raw_source_fetch_manifests[{index}].{path}" if path else f" at raw_source_fetch_manifests[{index}]"
        raise WorkbenchException(POWER_SYSTEM_RAW_FETCH_ERROR, f"Raw source fetch manifest schema violation{suffix}: {first.message}")


def _load_schema(schema_dir: Path) -> dict[str, Any]:
    path = schema_dir / "power_system_raw_fetch_manifest.schema.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkbenchException(POWER_SYSTEM_RAW_FETCH_ERROR, f"Missing raw source fetch manifest schema: {path}") from exc


def _records_hash(records: list[dict[str, Any]]) -> str:
    encoded = json.dumps(to_plain(records), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _query_fields(value: Any) -> list[str]:
    if value in {None, ""}:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _optional_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)
