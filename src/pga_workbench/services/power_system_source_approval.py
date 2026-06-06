from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from .fundamentals import load_pjm_fundamental_feeds
from .power_system_sources import load_power_system_source_catalog

POWER_SYSTEM_SOURCE_APPROVAL_ERROR = "POWER_SYSTEM_SOURCE_APPROVAL_ERROR"


def build_pjm_load_actual_feed_approval_report(
    registry_dir: Path,
    *,
    metadata_verification_report: dict[str, Any] | None = None,
    source_readiness_report: dict[str, Any] | None = None,
    feed_ids: list[str] | None = None,
) -> dict[str, Any]:
    registry_dir = Path(registry_dir)
    feeds = load_pjm_fundamental_feeds(registry_dir)
    selected = feed_ids or [
        feed_id
        for feed_id, feed in feeds.items()
        if feed.get("feed_class") in {"actual", "preliminary_actual"}
    ]
    metadata_verified = _metadata_verified_feed_ids(metadata_verification_report)
    source_rows = _source_row_counts_by_feed(source_readiness_report)
    publication_by_feed = _source_publication_by_feed(registry_dir)
    assessments = [
        _assess_feed(
            feed_id,
            feeds.get(feed_id),
            publication_by_feed.get(feed_id),
            metadata_verified=metadata_verified,
            source_rows=source_rows,
        )
        for feed_id in selected
    ]
    report = {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "product_family": "load",
        "approval_scope": "load_actual_source_feeds",
        "approved": all(item["approved"] for item in assessments),
        "feed_assessments": assessments,
        "contains_secret_values": False,
    }
    return report


def validate_source_feed_approval_report(report: dict[str, Any], schema_dir: Path) -> None:
    schema = load_yaml_unique(Path(schema_dir) / "power_system_source_feed_approval_report.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(report), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.path)
        suffix = f" at {path}" if path else ""
        raise WorkbenchException(POWER_SYSTEM_SOURCE_APPROVAL_ERROR, f"Source feed approval report schema violation{suffix}: {first.message}")


def _assess_feed(
    feed_id: str,
    feed: dict[str, Any] | None,
    publication: dict[str, Any] | None,
    *,
    metadata_verified: set[str],
    source_rows: dict[str, int],
) -> dict[str, Any]:
    blockers: list[str] = []
    if feed is None:
        return {
            "feed_id": feed_id,
            "data_miner_feed": None,
            "feed_status": "missing",
            "publication_id": None,
            "publication_status": None,
            "authoritative_use": None,
            "metadata_verified": False,
            "source_row_count": 0,
            "approved": False,
            "blockers": ["missing_feed_descriptor"],
        }
    if feed.get("feed_class") not in {"actual", "preliminary_actual"}:
        blockers.append("unsupported_feed_class_for_load_actual_approval")
    if feed.get("status") != "approved_core":
        blockers.append("feed_descriptor_not_approved_core")
    metadata_ok = feed_id in metadata_verified
    if not metadata_ok:
        blockers.append("metadata_verification_missing")
    row_count = int(source_rows.get(feed_id) or 0)
    if row_count < 1:
        blockers.append("source_row_evidence_missing")
    publication_id = None
    publication_status = None
    authoritative_use = None
    if publication is None:
        blockers.append("source_publication_missing")
    else:
        publication_id = str(publication.get("publication_id"))
        publication_status = publication.get("status")
        lifecycle = dict(publication.get("publication_lifecycle") or {})
        authoritative_use = lifecycle.get("authoritative_use")
        if publication_status != "approved_core":
            blockers.append("source_publication_not_approved_core")
        if authoritative_use != "approved_source_surface":
            blockers.append("source_publication_not_authoritative")
    return {
        "feed_id": feed_id,
        "data_miner_feed": feed.get("data_miner_feed"),
        "feed_status": feed.get("status"),
        "publication_id": publication_id,
        "publication_status": publication_status,
        "authoritative_use": authoritative_use,
        "metadata_verified": metadata_ok,
        "source_row_count": row_count,
        "approved": not blockers,
        "blockers": blockers,
    }


def _metadata_verified_feed_ids(report: dict[str, Any] | None) -> set[str]:
    if report is None:
        return set()
    if report.get("contains_secret_values") not in {None, False}:
        raise WorkbenchException(POWER_SYSTEM_SOURCE_APPROVAL_ERROR, "Metadata verification report must be redacted")
    return {
        str(item.get("registry_feed_id"))
        for item in report.get("verified_feeds") or []
        if isinstance(item, dict) and item.get("missing_fields", []) == []
    }


def _source_row_counts_by_feed(report: dict[str, Any] | None) -> dict[str, int]:
    if report is None:
        return {}
    if report.get("contains_secret_values") not in {None, False}:
        raise WorkbenchException(POWER_SYSTEM_SOURCE_APPROVAL_ERROR, "Source readiness report must be redacted")
    counts: dict[str, int] = {}
    for item in report.get("source_fetches") or []:
        if not isinstance(item, dict):
            continue
        feed_id = str(item.get("registry_feed_id") or "")
        if not feed_id:
            continue
        counts[feed_id] = counts.get(feed_id, 0) + int(item.get("row_count") or 0)
    return counts


def _source_publication_by_feed(registry_dir: Path) -> dict[str, dict[str, Any]]:
    catalog = load_power_system_source_catalog(registry_dir)
    mapped: dict[str, dict[str, Any]] = {}
    for publication_id, publication in catalog.items():
        record = {"publication_id": publication_id, **publication}
        for feed_id in publication.get("registry_feed_ids") or []:
            key = str(feed_id)
            if key in mapped:
                raise WorkbenchException(
                    POWER_SYSTEM_SOURCE_APPROVAL_ERROR,
                    f"Feed maps to multiple source publications: {key}",
                )
            mapped[key] = record
    return mapped
