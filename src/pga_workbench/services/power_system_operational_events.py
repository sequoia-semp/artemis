from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from .power_system_sources import load_power_system_source_catalog

POWER_SYSTEM_OPERATIONAL_EVENT_ERROR = "POWER_SYSTEM_OPERATIONAL_EVENT_ERROR"


def load_power_system_operational_event_feeds(registry_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_yaml_unique(Path(registry_dir) / "power_system_operational_event_feeds.yaml")
    if not isinstance(data, dict):
        raise WorkbenchException(POWER_SYSTEM_OPERATIONAL_EVENT_ERROR, "power_system_operational_event_feeds.yaml must be a mapping")
    return {str(key): dict(value) for key, value in data.items() if isinstance(value, dict)}


def approved_operational_event_feeds(registry_dir: Path) -> dict[str, dict[str, Any]]:
    feeds = load_power_system_operational_event_feeds(registry_dir)
    approved = {feed_id: record for feed_id, record in feeds.items() if record.get("status") == "approved_core"}
    for feed_id, record in approved.items():
        if record.get("normalization_status") != "approved_core":
            raise WorkbenchException(
                POWER_SYSTEM_OPERATIONAL_EVENT_ERROR,
                f"Approved operational event feed must have approved normalization status: {feed_id}",
            )
    return approved


def build_operational_event_candidate_plan(registry_dir: Path, *, operator_id: str = "PJM") -> dict[str, Any]:
    registry_dir = Path(registry_dir)
    feeds = load_power_system_operational_event_feeds(registry_dir)
    catalog = load_power_system_source_catalog(registry_dir)
    publications = []
    for publication_id, publication in sorted(catalog.items()):
        if publication.get("product_family") not in {"outages", "constraints"}:
            continue
        feed_ids = [str(item) for item in publication.get("registry_feed_ids") or []]
        feed_assessments = [_feed_assessment(feed_id, feeds.get(feed_id)) for feed_id in feed_ids]
        lifecycle = dict(publication.get("publication_lifecycle") or {})
        blockers = []
        if publication.get("status") != "approved_core":
            blockers.append("source_publication_not_approved_core")
        if lifecycle.get("authoritative_use") != "approved_source_surface":
            blockers.append("source_publication_not_authoritative")
        if lifecycle.get("revision_policy") == "source_specific_pending":
            blockers.append("source_publication_revision_policy_pending")
        if lifecycle.get("publication_finality") == "candidate_pending":
            blockers.append("source_publication_finality_pending")
        if any(not item["approved"] for item in feed_assessments):
            blockers.append("operational_event_feed_not_approved")
        publications.append(
            {
                "publication_id": publication_id,
                "publication_status": publication.get("status"),
                "product_family": publication.get("product_family"),
                "authoritative_use": lifecycle.get("authoritative_use"),
                "feed_ids": feed_ids,
                "feeds": feed_assessments,
                "approved": not blockers,
                "blockers": blockers,
            }
        )
    return {
        "operator_id": operator_id,
        "source_system": "pjm_data_miner_api",
        "approval_scope": "operational_event_candidate_plan",
        "approved": all(item["approved"] for item in publications) if publications else False,
        "publication_count": len(publications),
        "feed_count": sum(len(item["feeds"]) for item in publications),
        "publications": publications,
        "contains_secret_values": False,
    }


def validate_operational_event_candidate_plan(plan: dict[str, Any], schema_dir: Path) -> None:
    schema = load_yaml_unique(Path(schema_dir) / "power_system_operational_event_plan.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(plan), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.path)
        suffix = f" at {path}" if path else ""
        raise WorkbenchException(POWER_SYSTEM_OPERATIONAL_EVENT_ERROR, f"Operational event plan schema violation{suffix}: {first.message}")


def _feed_assessment(feed_id: str, feed: dict[str, Any] | None) -> dict[str, Any]:
    if feed is None:
        return {
            "feed_id": feed_id,
            "event_family": None,
            "event_class": None,
            "timestamp_policy": None,
            "identifier_policy": None,
            "topology_linkage": None,
            "normalization_status": None,
            "feed_status": None,
            "approved": False,
            "blockers": ["missing_operational_event_feed_descriptor"],
        }
    blockers = []
    if feed.get("status") != "approved_core":
        blockers.append("feed_not_approved_core")
    if feed.get("normalization_status") != "approved_core":
        blockers.append("normalization_not_approved")
    if feed.get("timestamp_policy") != "utc_delivery_windows_required":
        blockers.append("timestamp_policy_pending")
    if feed.get("identifier_policy") != "source_identity_approved":
        blockers.append("identifier_policy_pending")
    if feed.get("topology_linkage") != "approved":
        blockers.append("topology_linkage_not_approved")
    return {
        "feed_id": feed_id,
        "event_family": feed.get("event_family"),
        "event_class": feed.get("event_class"),
        "timestamp_policy": feed.get("timestamp_policy"),
        "identifier_policy": feed.get("identifier_policy"),
        "topology_linkage": feed.get("topology_linkage"),
        "normalization_status": feed.get("normalization_status"),
        "feed_status": feed.get("status"),
        "approved": not blockers,
        "blockers": blockers,
    }
