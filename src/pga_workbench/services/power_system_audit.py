from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from .power_system_ingestion import BUNDLE_METADATA_KEY, validate_power_system_artifact_bundle
from .redaction import assert_no_disallowed_secret_fields

POWER_SYSTEM_AUDIT_ERROR = "POWER_SYSTEM_AUDIT_ERROR"


def build_power_system_source_audit(bundle: dict[str, Any]) -> dict[str, Any]:
    validate_power_system_artifact_bundle(bundle)
    metadata = dict(bundle.get(BUNDLE_METADATA_KEY) or {})
    preflight = _optional_mapping(metadata.get("preflight"), "preflight")
    metadata_verification = _optional_mapping(metadata.get("metadata_verification"), "metadata_verification")
    source_readiness = _optional_mapping(metadata.get("source_readiness"), "source_readiness")
    source_publications = _optional_mapping(metadata.get("source_publications"), "source_publications")
    raw_source_fetches = _optional_mapping(metadata.get("raw_source_fetches"), "raw_source_fetches")
    operational_event_plan = _optional_mapping(metadata.get("operational_event_plan"), "operational_event_plan")
    _assert_redacted(preflight, "preflight")
    _assert_redacted(metadata_verification, "metadata_verification")
    _assert_redacted(source_readiness, "source_readiness")
    _assert_redacted(source_publications, "source_publications")
    _assert_redacted(raw_source_fetches, "raw_source_fetches")
    _assert_redacted(operational_event_plan, "operational_event_plan")

    source_fetch_rows = sum(int(item.get("row_count") or 0) for item in (source_readiness or {}).get("source_fetches") or [] if isinstance(item, dict))
    raw_fetch_manifest_count = int((raw_source_fetches or {}).get("manifest_count") or 0)
    publications = [item for item in (source_publications or {}).get("source_publications") or [] if isinstance(item, dict)]
    candidate_publication_count = sum(
        1
        for item in publications
        if (item.get("publication_lifecycle") or {}).get("authoritative_use") != "approved_source_surface"
    )
    blocked_operational_event_publication_count = int((operational_event_plan or {}).get("blocked_publication_count") or 0)
    blocked_operational_event_feed_count = int((operational_event_plan or {}).get("blocked_feed_count") or 0)

    blockers = []
    if preflight is not None and preflight.get("ready") is not True:
        blockers.append("preflight_not_ready")
    if source_readiness is not None and source_readiness.get("ready") is not True:
        blockers.append("source_readiness_not_ready")
    if candidate_publication_count:
        blockers.append("candidate_source_publications_present")
    if blocked_operational_event_publication_count or blocked_operational_event_feed_count:
        blockers.append("operational_events_not_approved")
    if raw_source_fetches is not None and raw_source_fetches.get("contains_raw_records") is not False:
        blockers.append("raw_source_fetch_evidence_unredacted")

    audit = {
        "audit_id": f"source-audit.{metadata.get('bundle_id')}",
        "bundle_id": str(metadata.get("bundle_id") or ""),
        "as_of": str(metadata.get("as_of") or ""),
        "operator_id": str(metadata.get("operator_id") or ""),
        "source_system": str(metadata.get("source_system") or ""),
        "data_environment": str(metadata.get("data_environment") or ""),
        "ready": not blockers,
        "blockers": blockers,
        "summary": {
            "source_fetch_rows": source_fetch_rows,
            "raw_fetch_manifest_count": raw_fetch_manifest_count,
            "candidate_publication_count": candidate_publication_count,
            "blocked_operational_event_publication_count": blocked_operational_event_publication_count,
            "blocked_operational_event_feed_count": blocked_operational_event_feed_count,
        },
        "preflight": preflight,
        "metadata_verification": metadata_verification,
        "source_readiness": source_readiness,
        "source_publications": source_publications,
        "raw_source_fetches": raw_source_fetches,
        "operational_event_plan": operational_event_plan,
        "contains_raw_records": False,
        "contains_secret_values": False,
    }
    return audit


def validate_power_system_source_audit(audit: dict[str, Any], schema_dir: Path) -> None:
    schema = load_yaml_unique(Path(schema_dir) / "power_system_source_audit.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(audit), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.path)
        suffix = f" at {path}" if path else ""
        raise WorkbenchException(POWER_SYSTEM_AUDIT_ERROR, f"Power-system source audit schema violation{suffix}: {first.message}")


def _optional_mapping(value: Any, label: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise WorkbenchException(POWER_SYSTEM_AUDIT_ERROR, f"Source audit {label} evidence must be a mapping")
    return dict(value)


def _assert_redacted(value: dict[str, Any] | None, label: str) -> None:
    if value is None:
        return
    if value.get("contains_secret_values") is not False:
        raise WorkbenchException(POWER_SYSTEM_AUDIT_ERROR, f"Source audit {label} evidence must be redacted")
    if value.get("contains_raw_records") is not None and value.get("contains_raw_records") is not False:
        raise WorkbenchException(POWER_SYSTEM_AUDIT_ERROR, f"Source audit {label} evidence must not contain raw records")
    assert_no_disallowed_secret_fields(value, label=f"Source audit {label}", error_code=POWER_SYSTEM_AUDIT_ERROR)
