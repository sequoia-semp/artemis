from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique

POWER_SYSTEM_SOURCE_ERROR = "POWER_SYSTEM_SOURCE_ERROR"
LOCAL_ONLY_DATA_ENVIRONMENTS = {"development", "fixture", "local", "test"}


def load_power_system_source_catalog(registry_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_yaml_unique(Path(registry_dir) / "power_system_source_catalog.yaml")
    if not isinstance(data, dict):
        raise WorkbenchException(POWER_SYSTEM_SOURCE_ERROR, "Power system source catalog must be a mapping")
    return {str(key): dict(value) for key, value in data.items() if isinstance(value, dict)}


def load_known_power_feed_ids(registry_dir: Path) -> set[str]:
    registry_dir = Path(registry_dir)
    feed_ids: set[str] = set()
    for name in ["pjm_fundamental_feeds.yaml", "power_system_price_feeds.yaml", "power_generation_mix_feeds.yaml", "power_system_operational_event_feeds.yaml"]:
        path = registry_dir / name
        if not path.exists():
            continue
        data = load_yaml_unique(path)
        if isinstance(data, dict):
            feed_ids.update(str(key) for key in data)
    return feed_ids


def validate_power_system_source_catalog_references(registry_dir: Path) -> dict[str, list[str]]:
    catalog = load_power_system_source_catalog(registry_dir)
    known_feed_ids = load_known_power_feed_ids(registry_dir)
    resolved: dict[str, list[str]] = {}
    for publication_id, record in catalog.items():
        _validate_publication_lifecycle(publication_id, record)
        registry_feed_ids = [str(item) for item in record.get("registry_feed_ids", [])]
        if record.get("status") == "approved_core" and not registry_feed_ids:
            raise WorkbenchException(
                POWER_SYSTEM_SOURCE_ERROR,
                f"Approved source publication {publication_id} must reference normalized feed descriptors",
            )
        missing = [feed_id for feed_id in registry_feed_ids if feed_id not in known_feed_ids]
        if missing:
            raise WorkbenchException(
                POWER_SYSTEM_SOURCE_ERROR,
                f"Source publication {publication_id} references unknown feed descriptors: {', '.join(missing)}",
            )
        resolved[publication_id] = registry_feed_ids
    return resolved


def source_publication_lifecycle_summary(registry_dir: Path) -> dict[str, dict[str, Any]]:
    catalog = load_power_system_source_catalog(registry_dir)
    return {
        publication_id: {
            "status": record.get("status"),
            "product_family": record.get("product_family"),
            **dict(record.get("publication_lifecycle") or {}),
        }
        for publication_id, record in catalog.items()
    }


def build_power_system_source_publication_report(
    registry_dir: Path,
    *,
    registry_feed_ids: list[str] | None = None,
    operator_id: str | None = None,
    source_system: str | None = None,
) -> dict[str, Any]:
    validate_power_system_source_catalog_references(registry_dir)
    catalog = load_power_system_source_catalog(registry_dir)
    selected_feed_ids = {str(item) for item in registry_feed_ids or []}
    publications: list[dict[str, Any]] = []
    for publication_id, record in sorted(catalog.items()):
        record_feed_ids = [str(item) for item in record.get("registry_feed_ids") or []]
        if selected_feed_ids and not selected_feed_ids.intersection(record_feed_ids):
            continue
        publications.append(
            {
                "publication_id": publication_id,
                "status": record.get("status"),
                "product_family": record.get("product_family"),
                "registry_feed_ids": record_feed_ids,
                "canonical_roles": list(record.get("canonical_roles") or []),
                "publication_lifecycle": dict(record.get("publication_lifecycle") or {}),
            }
        )
    if selected_feed_ids and not publications:
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_ERROR,
            f"No source publications matched feed ids: {', '.join(sorted(selected_feed_ids))}",
        )
    return {
        "operator_id": operator_id,
        "source_system": source_system,
        "selected_registry_feed_ids": sorted(selected_feed_ids),
        "publication_count": len(publications),
        "source_publications": publications,
        "contains_secret_values": False,
    }


def validate_state_pack_source_publication_publish_status(artifacts: dict[str, Any]) -> None:
    if not isinstance(artifacts, dict):
        raise WorkbenchException(POWER_SYSTEM_SOURCE_ERROR, "State-pack artifacts must be a mapping for source publication validation")
    metadata = artifacts.get("power_system_artifact_bundle")
    if not isinstance(metadata, dict):
        return
    source_publications = metadata.get("source_publications")
    if source_publications is None:
        return
    if not isinstance(source_publications, dict):
        raise WorkbenchException(POWER_SYSTEM_SOURCE_ERROR, "Source publication evidence must be a mapping")
    if source_publications.get("contains_secret_values") is not False:
        raise WorkbenchException(POWER_SYSTEM_SOURCE_ERROR, "Source publication evidence must be redacted before publish")
    data_environment = str(metadata.get("data_environment") or "").lower()
    if data_environment in LOCAL_ONLY_DATA_ENVIRONMENTS:
        return
    blocked: list[str] = []
    for item in source_publications.get("source_publications") or []:
        if not isinstance(item, dict):
            raise WorkbenchException(POWER_SYSTEM_SOURCE_ERROR, "Source publication evidence entries must be mappings")
        lifecycle = dict(item.get("publication_lifecycle") or {})
        if item.get("status") != "approved_core" or lifecycle.get("authoritative_use") != "approved_source_surface":
            blocked.append(str(item.get("publication_id") or "unknown"))
    if blocked:
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_ERROR,
            "Source publications are not approved for accepted state-pack publish: " + ", ".join(sorted(blocked)),
        )
    required_feed_ids = _required_publish_evidence_feed_ids(source_publications)
    if required_feed_ids:
        _validate_source_publication_publish_evidence(metadata, required_feed_ids)


def _required_publish_evidence_feed_ids(source_publications: dict[str, Any]) -> set[str]:
    approved_feed_ids: set[str] = set()
    for item in source_publications.get("source_publications") or []:
        if not isinstance(item, dict):
            raise WorkbenchException(POWER_SYSTEM_SOURCE_ERROR, "Source publication evidence entries must be mappings")
        lifecycle = dict(item.get("publication_lifecycle") or {})
        if item.get("status") == "approved_core" and lifecycle.get("authoritative_use") == "approved_source_surface":
            approved_feed_ids.update(str(feed_id) for feed_id in item.get("registry_feed_ids") or [] if str(feed_id))
    selected_feed_ids = {str(feed_id) for feed_id in source_publications.get("selected_registry_feed_ids") or [] if str(feed_id)}
    if selected_feed_ids:
        return approved_feed_ids.intersection(selected_feed_ids)
    return approved_feed_ids


def _validate_source_publication_publish_evidence(metadata: dict[str, Any], required_feed_ids: set[str]) -> None:
    source_readiness = metadata.get("source_readiness")
    metadata_verification = metadata.get("metadata_verification")
    raw_source_fetches = metadata.get("raw_source_fetches")
    missing_sections = [
        label
        for label, value in [
            ("source_readiness", source_readiness),
            ("metadata_verification", metadata_verification),
            ("raw_source_fetches", raw_source_fetches),
        ]
        if not isinstance(value, dict)
    ]
    if missing_sections:
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_ERROR,
            "Approved source publications require publish evidence sections: " + ", ".join(missing_sections),
        )
    for label, value in [
        ("source readiness", source_readiness),
        ("metadata verification", metadata_verification),
        ("raw source fetch", raw_source_fetches),
    ]:
        if value.get("contains_secret_values") is not False:
            raise WorkbenchException(POWER_SYSTEM_SOURCE_ERROR, f"Approved source publication {label} evidence must be redacted")
    if raw_source_fetches.get("contains_raw_records") is not False:
        raise WorkbenchException(POWER_SYSTEM_SOURCE_ERROR, "Approved source publication raw source fetch evidence must not contain raw records")
    if source_readiness.get("ready") is not True or int(source_readiness.get("blocker_count") or 0) != 0:
        raise WorkbenchException(POWER_SYSTEM_SOURCE_ERROR, "Approved source publications require ready source-readiness evidence")
    if source_readiness.get("fetch_source_rows") is not True:
        raise WorkbenchException(POWER_SYSTEM_SOURCE_ERROR, "Approved source publications require source row fetch evidence")

    metadata_feed_ids = {
        str(item.get("registry_feed_id"))
        for item in metadata_verification.get("verified_feeds") or []
        if isinstance(item, dict) and item.get("registry_feed_id")
    }
    readiness_feed_ids = {
        str(item.get("registry_feed_id"))
        for item in source_readiness.get("source_fetches") or []
        if isinstance(item, dict)
        and item.get("registry_feed_id")
        and item.get("status") == "success"
        and int(item.get("row_count") or 0) > 0
        and int(item.get("page_count") or 0) > 0
        and item.get("truncated_by_max_pages") is not True
    }
    raw_fetch_feed_ids = {
        str(item.get("registry_feed_id"))
        for item in raw_source_fetches.get("manifests") or []
        if isinstance(item, dict)
        and item.get("registry_feed_id")
        and int(item.get("row_count") or 0) > 0
        and int(item.get("page_count") or 0) > 0
        and item.get("truncated_by_max_pages") is not True
    }
    if not raw_fetch_feed_ids:
        raw_fetch_feed_ids = {str(feed_id) for feed_id in raw_source_fetches.get("registry_feed_ids") or [] if str(feed_id)}
    missing: list[str] = []
    for feed_id in sorted(required_feed_ids):
        if feed_id not in metadata_feed_ids:
            missing.append(f"{feed_id}:metadata_verification")
        if feed_id not in readiness_feed_ids:
            missing.append(f"{feed_id}:source_readiness")
        if feed_id not in raw_fetch_feed_ids:
            missing.append(f"{feed_id}:raw_source_fetches")
    if missing:
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_ERROR,
            "Approved source publications lack matching publish evidence: " + ", ".join(missing),
        )


def _validate_publication_lifecycle(publication_id: str, record: dict[str, Any]) -> None:
    lifecycle = record.get("publication_lifecycle")
    if not isinstance(lifecycle, dict):
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_ERROR,
            f"Source publication {publication_id} must declare publication_lifecycle",
        )
    if record.get("status") != "approved_core":
        return
    pending_fields = [
        key
        for key, value in lifecycle.items()
        if value in {"source_specific_pending", "candidate_pending", "candidate_only", "deferred"}
    ]
    if pending_fields:
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_ERROR,
            f"Approved source publication {publication_id} has unresolved lifecycle fields: {', '.join(sorted(pending_fields))}",
        )
    if lifecycle.get("authoritative_use") != "approved_source_surface":
        raise WorkbenchException(
            POWER_SYSTEM_SOURCE_ERROR,
            f"Approved source publication {publication_id} must allow approved_source_surface authoritative use",
        )
