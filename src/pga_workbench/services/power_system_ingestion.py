from __future__ import annotations

from typing import Any

from ..exceptions import WorkbenchException
from .artifact_composition import compose_artifact_payloads, validate_artifact_composition_metadata

POWER_SYSTEM_INGESTION_ERROR = "POWER_SYSTEM_INGESTION_ERROR"
BUNDLE_METADATA_KEY = "power_system_artifact_bundle"


def build_power_system_artifact_bundle(
    *payloads: dict[str, Any],
    bundle_id: str,
    as_of: str,
    operator_id: str,
    source_system: str,
    data_environment: str = "production",
    preflight_report: dict[str, Any] | None = None,
    metadata_verification_report: dict[str, Any] | None = None,
    source_readiness_report: dict[str, Any] | None = None,
    source_publication_report: dict[str, Any] | None = None,
    operational_event_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not payloads:
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "At least one artifact payload is required for a bundle")
    composed = compose_artifact_payloads(*payloads)
    composed[BUNDLE_METADATA_KEY] = {
        "bundle_id": bundle_id,
        "as_of": as_of,
        "operator_id": operator_id,
        "source_system": source_system,
        "data_environment": data_environment,
        "payload_count": len(payloads),
        "composition_product_keys": list(composed["artifact_composition"]["composition_product_keys"]),
        "view_fields": list(composed["artifact_composition"]["view_fields"]),
    }
    raw_source_fetch_manifests = composed.get("raw_source_fetch_manifests")
    if raw_source_fetch_manifests is not None:
        composed[BUNDLE_METADATA_KEY]["raw_source_fetches"] = _raw_source_fetch_manifest_evidence(raw_source_fetch_manifests)
    if preflight_report is not None:
        composed[BUNDLE_METADATA_KEY]["preflight"] = _preflight_evidence(preflight_report)
    if metadata_verification_report is not None:
        composed[BUNDLE_METADATA_KEY]["metadata_verification"] = _metadata_verification_evidence(metadata_verification_report)
    if source_readiness_report is not None:
        composed[BUNDLE_METADATA_KEY]["source_readiness"] = _source_readiness_evidence(source_readiness_report)
    if source_publication_report is not None:
        composed[BUNDLE_METADATA_KEY]["source_publications"] = _source_publication_evidence(source_publication_report)
    if operational_event_plan is not None:
        composed[BUNDLE_METADATA_KEY]["operational_event_plan"] = _operational_event_plan_evidence(operational_event_plan)
    validate_power_system_artifact_bundle(composed)
    return composed


def validate_power_system_artifact_bundle(bundle: dict[str, Any]) -> None:
    if not isinstance(bundle, dict):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Power system artifact bundle must be a mapping")
    metadata = bundle.get(BUNDLE_METADATA_KEY)
    if not isinstance(metadata, dict):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, f"Power system artifact bundle missing {BUNDLE_METADATA_KEY}")
    validate_artifact_composition_metadata(bundle)
    expected_keys = list(bundle["artifact_composition"]["composition_product_keys"])
    if metadata.get("composition_product_keys") != expected_keys:
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle composition product keys do not match artifact composition metadata")
    if int(metadata.get("payload_count") or 0) != int(bundle["artifact_composition"]["payload_count"]):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle payload count does not match artifact composition metadata")
    preflight = metadata.get("preflight")
    if preflight is not None:
        if not isinstance(preflight, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle preflight evidence must be a mapping")
        if preflight.get("contains_secret_values") is not False:
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle preflight evidence must be redacted")
    metadata_verification = metadata.get("metadata_verification")
    if metadata_verification is not None:
        if not isinstance(metadata_verification, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle metadata verification evidence must be a mapping")
        if metadata_verification.get("contains_secret_values") is not False:
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle metadata verification evidence must be redacted")
    source_readiness = metadata.get("source_readiness")
    if source_readiness is not None:
        if not isinstance(source_readiness, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle source readiness evidence must be a mapping")
        if source_readiness.get("contains_secret_values") is not False:
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle source readiness evidence must be redacted")
    source_publications = metadata.get("source_publications")
    if source_publications is not None:
        if not isinstance(source_publications, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle source publication evidence must be a mapping")
        if source_publications.get("contains_secret_values") is not False:
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle source publication evidence must be redacted")
    raw_source_fetches = metadata.get("raw_source_fetches")
    if raw_source_fetches is not None:
        if not isinstance(raw_source_fetches, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle raw source fetch evidence must be a mapping")
        if raw_source_fetches.get("contains_raw_records") is not False or raw_source_fetches.get("contains_secret_values") is not False:
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle raw source fetch evidence must be redacted")
    operational_event_plan = metadata.get("operational_event_plan")
    if operational_event_plan is not None:
        if not isinstance(operational_event_plan, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle operational event plan evidence must be a mapping")
        if operational_event_plan.get("contains_secret_values") is not False:
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Bundle operational event plan evidence must be redacted")


def _preflight_evidence(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Preflight report must be a mapping")
    credential_checks = dict(report.get("credential_checks") or {})
    redacted_credentials = {
        key: {
            "configured": bool(value.get("configured")) if isinstance(value, dict) else False,
            "value_redacted": True,
        }
        for key, value in credential_checks.items()
    }
    return {
        "operator_id": report.get("operator_id"),
        "source_system": report.get("source_system"),
        "ready": bool(report.get("ready")),
        "blocker_count": len(report.get("blockers") or []),
        "selected_feeds": dict(report.get("selected_feeds") or {}),
        "query_plan": _compact_query_plan_evidence(report.get("query_plan"), label="preflight query_plan"),
        "query_plans": _compact_query_plans_evidence(report.get("query_plans")),
        "credential_checks": redacted_credentials,
        "contains_secret_values": False,
    }


def _raw_source_fetch_manifest_evidence(manifests: Any) -> dict[str, Any]:
    if not isinstance(manifests, list):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Raw source fetch manifests must be a list")
    compact_manifests: list[dict[str, Any]] = []
    surface_counts: dict[str, int] = {}
    feed_ids: list[str] = []
    query_plan_ids: list[str] = []
    total_row_count = 0
    total_page_count = 0
    truncated_count = 0
    for item in manifests:
        if not isinstance(item, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Raw source fetch manifest evidence must be a mapping")
        if item.get("contains_raw_records") is not False or item.get("contains_secret_values") is not False:
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Raw source fetch manifest evidence must be redacted")
        source_surface = str(item.get("source_surface") or "")
        registry_feed_id = str(item.get("registry_feed_id") or "")
        query_plan_id = str(item.get("query_plan_id") or "")
        row_count = int(item.get("row_count") or 0)
        page_count = int(item.get("page_count") or 0)
        total_row_count += row_count
        total_page_count += page_count
        if item.get("truncated_by_max_pages"):
            truncated_count += 1
        if source_surface:
            surface_counts[source_surface] = surface_counts.get(source_surface, 0) + 1
        if registry_feed_id and registry_feed_id not in feed_ids:
            feed_ids.append(registry_feed_id)
        if query_plan_id and query_plan_id not in query_plan_ids:
            query_plan_ids.append(query_plan_id)
        compact_manifests.append(
            {
                "manifest_id": item.get("manifest_id"),
                "source_surface": item.get("source_surface"),
                "registry_feed_id": item.get("registry_feed_id"),
                "source_feed": item.get("source_feed"),
                "request_id": item.get("request_id"),
                "request_kind": item.get("request_kind"),
                "query_plan_id": item.get("query_plan_id"),
                "window_start": item.get("window_start"),
                "window_end": item.get("window_end"),
                "pnode_id": item.get("pnode_id"),
                "row_count": row_count,
                "page_count": page_count,
                "truncated_by_max_pages": bool(item.get("truncated_by_max_pages")),
                "raw_records_sha256": item.get("raw_records_sha256"),
            }
        )
    return {
        "manifest_count": len(compact_manifests),
        "total_row_count": total_row_count,
        "total_page_count": total_page_count,
        "truncated_manifest_count": truncated_count,
        "source_surface_counts": dict(sorted(surface_counts.items())),
        "registry_feed_ids": sorted(feed_ids),
        "query_plan_ids": sorted(query_plan_ids),
        "manifests": compact_manifests,
        "contains_raw_records": False,
        "contains_secret_values": False,
    }


def _compact_query_plans_evidence(value: Any) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Preflight query_plans evidence must be a mapping")
    compact: dict[str, dict[str, Any]] = {}
    for surface, plan in value.items():
        compact[str(surface)] = _compact_query_plan_evidence(plan, label=f"preflight query_plans.{surface}") or {}
    return compact


def _compact_query_plan_evidence(value: Any, *, label: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, f"{label} evidence must be a mapping")
    if value.get("contains_secret_values") is not None and value.get("contains_secret_values") is not False:
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, f"{label} evidence must be redacted")
    allowed = [
        "plan_id",
        "planned_request_count",
        "built_request_count",
        "max_connections_per_minute",
        "account_class",
        "windows",
        "lineage",
    ]
    return {key: value[key] for key in allowed if key in value}


def _metadata_verification_evidence(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Metadata verification report must be a mapping")
    verified_feeds = report.get("verified_feeds") or []
    if not isinstance(verified_feeds, list):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Metadata verification verified_feeds must be a list")
    compact_feeds: list[dict[str, Any]] = []
    for item in verified_feeds:
        if not isinstance(item, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Metadata verification feed evidence must be a mapping")
        compact_feeds.append(
            {
                "registry_feed_id": item.get("registry_feed_id"),
                "data_miner_feed": item.get("data_miner_feed"),
                "required_field_count": int(item.get("required_field_count") or 0),
                "observed_field_count": int(item.get("observed_field_count") or 0),
            }
        )
    return {
        "operator_id": report.get("operator_id"),
        "source_system": report.get("source_system"),
        "definition_source": report.get("definition_source"),
        "verified_feed_count": int(report.get("verified_feed_count") or len(compact_feeds)),
        "include_candidate": bool(report.get("include_candidate")),
        "verified_feeds": compact_feeds,
        "contains_secret_values": False,
    }


def _source_readiness_evidence(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Source readiness report must be a mapping")
    source_fetches = report.get("source_fetches") or []
    if not isinstance(source_fetches, list):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Source readiness source_fetches must be a list")
    compact_fetches: list[dict[str, Any]] = []
    for item in source_fetches:
        if not isinstance(item, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Source readiness fetch evidence must be a mapping")
        compact_fetch = {
            "status": item.get("status"),
            "product_family": item.get("product_family"),
            "registry_feed_id": item.get("registry_feed_id"),
            "data_miner_feed": item.get("data_miner_feed"),
            "row_count": int(item.get("row_count") or 0),
            "page_count": int(item.get("page_count") or 0),
            "truncated_by_max_pages": bool(item.get("truncated_by_max_pages")),
        }
        if item.get("status") == "error":
            compact_fetch["error_code"] = item.get("error_code")
        compact_fetches.append(compact_fetch)
    query_execution = report.get("query_execution")
    compact_query_execution = None
    if query_execution is not None:
        if not isinstance(query_execution, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Source readiness query_execution must be a mapping")
        if query_execution.get("contains_secret_values") is not False:
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Source readiness query_execution must be redacted")
        compact_query_execution = {
            "plan_id": query_execution.get("plan_id"),
            "planned_request_count": int(query_execution.get("planned_request_count") or 0),
            "built_request_count": int(query_execution.get("built_request_count") or 0),
            "account_class": query_execution.get("account_class"),
            "max_connections_per_minute": int(query_execution.get("max_connections_per_minute") or 0),
            "request_kinds": dict(query_execution.get("request_kinds") or {}),
            "registry_feed_ids": list(query_execution.get("registry_feed_ids") or []),
            "pnode_ids": list(query_execution.get("pnode_ids") or []),
            "date_windows": list(query_execution.get("date_windows") or []),
            "contains_secret_values": False,
        }
    return {
        "operator_id": report.get("operator_id"),
        "source_system": report.get("source_system"),
        "ready": bool(report.get("ready")),
        "blocker_count": len(report.get("blockers") or []),
        "fetch_source_rows": bool(report.get("fetch_source_rows")),
        "source_fetches": compact_fetches,
        "query_execution": compact_query_execution,
        "contains_secret_values": False,
    }


def _source_publication_evidence(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Source publication report must be a mapping")
    source_publications = report.get("source_publications") or []
    if not isinstance(source_publications, list):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Source publication source_publications must be a list")
    compact_publications: list[dict[str, Any]] = []
    for item in source_publications:
        if not isinstance(item, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Source publication evidence must be a mapping")
        compact_publications.append(
            {
                "publication_id": item.get("publication_id"),
                "status": item.get("status"),
                "product_family": item.get("product_family"),
                "registry_feed_ids": list(item.get("registry_feed_ids") or []),
                "canonical_roles": list(item.get("canonical_roles") or []),
                "publication_lifecycle": dict(item.get("publication_lifecycle") or {}),
            }
        )
    return {
        "operator_id": report.get("operator_id"),
        "source_system": report.get("source_system"),
        "selected_registry_feed_ids": list(report.get("selected_registry_feed_ids") or []),
        "publication_count": int(report.get("publication_count") or len(compact_publications)),
        "source_publications": compact_publications,
        "contains_secret_values": False,
    }


def _operational_event_plan_evidence(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Operational event plan must be a mapping")
    if plan.get("contains_secret_values") is not False:
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Operational event plan must be redacted")
    publications = plan.get("publications") or []
    if not isinstance(publications, list):
        raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Operational event plan publications must be a list")
    compact_publications: list[dict[str, Any]] = []
    blocked_feed_count = 0
    for item in publications:
        if not isinstance(item, dict):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Operational event publication evidence must be a mapping")
        feeds = item.get("feeds") or []
        if not isinstance(feeds, list):
            raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Operational event publication feeds must be a list")
        compact_feeds: list[dict[str, Any]] = []
        for feed in feeds:
            if not isinstance(feed, dict):
                raise WorkbenchException(POWER_SYSTEM_INGESTION_ERROR, "Operational event feed evidence must be a mapping")
            if feed.get("approved") is not True:
                blocked_feed_count += 1
            compact_feeds.append(
                {
                    "feed_id": feed.get("feed_id"),
                    "event_family": feed.get("event_family"),
                    "event_class": feed.get("event_class"),
                    "feed_status": feed.get("feed_status"),
                    "normalization_status": feed.get("normalization_status"),
                    "topology_linkage": feed.get("topology_linkage"),
                    "approved": bool(feed.get("approved")),
                    "blockers": list(feed.get("blockers") or []),
                }
            )
        compact_publications.append(
            {
                "publication_id": item.get("publication_id"),
                "publication_status": item.get("publication_status"),
                "product_family": item.get("product_family"),
                "authoritative_use": item.get("authoritative_use"),
                "approved": bool(item.get("approved")),
                "blockers": list(item.get("blockers") or []),
                "feed_ids": list(item.get("feed_ids") or []),
                "feeds": compact_feeds,
            }
        )
    return {
        "operator_id": plan.get("operator_id"),
        "source_system": plan.get("source_system"),
        "approval_scope": plan.get("approval_scope"),
        "approved": bool(plan.get("approved")),
        "publication_count": int(plan.get("publication_count") or len(compact_publications)),
        "feed_count": int(plan.get("feed_count") or sum(len(item.get("feeds") or []) for item in compact_publications)),
        "blocked_publication_count": sum(1 for item in compact_publications if item["approved"] is not True),
        "blocked_feed_count": blocked_feed_count,
        "publications": compact_publications,
        "contains_secret_values": False,
    }
