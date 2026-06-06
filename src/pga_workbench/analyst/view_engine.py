from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from ..core.time import utc_now_iso
from ..data.contracts import assert_data_environment_allowed
from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from ..serialization import to_plain
from ..skills.validator import load_skill_ids
from .horizons import plus_minus_days, single_day_horizon
from .view_models import DataQuality, Stance, empty_section_for

VIEW_ERROR = "VIEW_ERROR"


def normalize_template_id(template_id: str) -> str:
    return template_id.replace("-", "_")


def _validate(schema: dict[str, Any], payload: dict[str, Any], label: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.path)
        suffix = f" at {path}" if path else ""
        raise WorkbenchException(VIEW_ERROR, f"{label}{suffix}: {first.message}")


def load_view_template(repo_root: Path, template_id: str) -> dict[str, Any]:
    repo_root = Path(repo_root)
    normalized = normalize_template_id(template_id)
    manifest = load_yaml_unique(repo_root / "views" / "manifest.yaml")
    for item in manifest.get("templates") or []:
        if item.get("id") == normalized:
            payload = load_yaml_unique(repo_root / "views" / str(item["path"]))
            if not isinstance(payload, dict):
                raise WorkbenchException(VIEW_ERROR, f"View template must be a mapping: {template_id}")
            return payload
    raise WorkbenchException(VIEW_ERROR, f"Unknown view template: {template_id}")


def _merge_view_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_view_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def merge_hot_state_artifacts(input_payload: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    state_payload = artifacts.get("view_payload") if isinstance(artifacts.get("view_payload"), dict) else {}
    merged = _merge_view_dicts(dict(state_payload), input_payload)

    state_inputs = artifacts.get("inputs") if isinstance(artifacts.get("inputs"), dict) else {}
    supplied_inputs = input_payload.get("inputs") if isinstance(input_payload.get("inputs"), dict) else {}
    if state_inputs or supplied_inputs:
        merged["inputs"] = _merge_view_dicts(dict(state_inputs), dict(supplied_inputs))

    for field in [
        "drivers",
        "driver_deltas",
        "forecast_actual_diffs",
        "scenarios",
        "prior_day_retrospective",
        "current_day_view",
        "fourteen_day_outlook",
        "summary",
        "stance_summary",
        "market_scope",
    ]:
        if field in artifacts and field not in input_payload:
            merged[field] = artifacts[field]

    if "evidence" not in input_payload:
        evidence = list(artifacts.get("evidence") or []) if isinstance(artifacts.get("evidence"), list) else []
        evidence.extend(_power_system_bundle_evidence(artifacts))
        if evidence:
            merged["evidence"] = evidence

    lineage = []
    if isinstance(artifacts.get("source_lineage"), list):
        lineage.extend(artifacts["source_lineage"])
    if isinstance(input_payload.get("source_lineage"), list):
        lineage.extend(input_payload["source_lineage"])
    if artifacts:
        lineage.append({"source": "hot_state", "artifact_keys": sorted(str(key) for key in artifacts)})
    if lineage:
        merged["source_lineage"] = lineage
    return merged


def _power_system_bundle_evidence(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = artifacts.get("power_system_artifact_bundle")
    if not isinstance(metadata, dict):
        return []
    evidence: list[dict[str, Any]] = []
    preflight = metadata.get("preflight")
    if isinstance(preflight, dict):
        evidence.append(
            {
                "artifact": "power_system_artifact_bundle",
                "evidence_type": "source_preflight",
                "operator_id": metadata.get("operator_id"),
                "source_system": metadata.get("source_system"),
                "ready": bool(preflight.get("ready")),
                "blocker_count": int(preflight.get("blocker_count") or 0),
                "selected_feeds": dict(preflight.get("selected_feeds") or {}),
                "contains_secret_values": False,
            }
        )
    metadata_verification = metadata.get("metadata_verification")
    if isinstance(metadata_verification, dict):
        evidence.append(
            {
                "artifact": "power_system_artifact_bundle",
                "evidence_type": "source_metadata_verification",
                "operator_id": metadata.get("operator_id"),
                "source_system": metadata.get("source_system"),
                "definition_source": metadata_verification.get("definition_source"),
                "verified_feed_count": int(metadata_verification.get("verified_feed_count") or 0),
                "contains_secret_values": False,
            }
        )
    source_readiness = metadata.get("source_readiness")
    if isinstance(source_readiness, dict):
        evidence.append(
            {
                "artifact": "power_system_artifact_bundle",
                "evidence_type": "source_readiness",
                "operator_id": metadata.get("operator_id"),
                "source_system": metadata.get("source_system"),
                "ready": bool(source_readiness.get("ready")),
                "blocker_count": int(source_readiness.get("blocker_count") or 0),
                "fetch_source_rows": bool(source_readiness.get("fetch_source_rows")),
                "source_fetch_count": len(source_readiness.get("source_fetches") or []),
                "contains_secret_values": False,
            }
        )
    source_publications = metadata.get("source_publications")
    if isinstance(source_publications, dict):
        publications = [item for item in source_publications.get("source_publications") or [] if isinstance(item, dict)]
        candidate_count = sum(
            1
            for item in publications
            if (item.get("publication_lifecycle") or {}).get("authoritative_use") != "approved_source_surface"
        )
        evidence.append(
            {
                "artifact": "power_system_artifact_bundle",
                "evidence_type": "source_publications",
                "operator_id": metadata.get("operator_id"),
                "source_system": metadata.get("source_system"),
                "publication_count": int(source_publications.get("publication_count") or len(publications)),
                "candidate_publication_count": candidate_count,
                "contains_secret_values": False,
            }
        )
    raw_fetches = metadata.get("raw_source_fetches")
    if isinstance(raw_fetches, dict):
        evidence.append(
            {
                "artifact": "power_system_artifact_bundle",
                "evidence_type": "raw_source_fetches",
                "operator_id": metadata.get("operator_id"),
                "source_system": metadata.get("source_system"),
                "manifest_count": int(raw_fetches.get("manifest_count") or 0),
                "total_row_count": int(raw_fetches.get("total_row_count") or 0),
                "truncated_manifest_count": int(raw_fetches.get("truncated_manifest_count") or 0),
                "source_surface_counts": dict(raw_fetches.get("source_surface_counts") or {}),
                "contains_raw_records": False,
                "contains_secret_values": False,
            }
        )
    operational_event_plan = metadata.get("operational_event_plan")
    if isinstance(operational_event_plan, dict):
        evidence.append(
            {
                "artifact": "power_system_artifact_bundle",
                "evidence_type": "operational_event_plan",
                "operator_id": metadata.get("operator_id"),
                "source_system": metadata.get("source_system"),
                "approved": bool(operational_event_plan.get("approved")),
                "publication_count": int(operational_event_plan.get("publication_count") or 0),
                "feed_count": int(operational_event_plan.get("feed_count") or 0),
                "blocked_publication_count": int(operational_event_plan.get("blocked_publication_count") or 0),
                "blocked_feed_count": int(operational_event_plan.get("blocked_feed_count") or 0),
                "contains_secret_values": False,
            }
        )
    return evidence


def _horizon_for(view_type: str, as_of: date) -> dict[str, str]:
    if view_type == "fourteen_day_fundamentals":
        return plus_minus_days(as_of).to_dict()
    if view_type == "prior_day_retrospective":
        return single_day_horizon(as_of, "prior_day").to_dict()
    return single_day_horizon(as_of, "current_day").to_dict()


def build_view(
    repo_root: Path,
    template_id: str,
    input_payload: dict[str, Any],
    as_of: str | None = None,
    allow_fixture: bool = False,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    template = load_view_template(repo_root, template_id)
    view_type = str(template["view_type"])
    as_of_date = date.fromisoformat(str(as_of or input_payload.get("as_of")))
    data_environment = str(input_payload.get("data_environment") or "development")
    assert_data_environment_allowed("analyst", data_environment, allow_fixture=allow_fixture)

    supplied_inputs = input_payload.get("inputs") or {}
    if not isinstance(supplied_inputs, dict):
        raise WorkbenchException(VIEW_ERROR, "View inputs must be a mapping")
    required_inputs = list(template.get("required_inputs") or [])
    missing_inputs = [name for name in required_inputs if name not in supplied_inputs]
    market_scope = input_payload.get("market_scope") or {
        "commodity": "power",
        "regions": ["PJM"],
        "exchange_scope": [],
    }
    if "exchange_scope" not in market_scope:
        market_scope = {**market_scope, "exchange_scope": []}

    stance = Stance(summary=str(input_payload.get("stance_summary") or "Insufficient live inputs for authoritative stance; output is schema-valid from supplied inputs."))
    data_quality = DataQuality(
        missing_required_inputs=missing_inputs,
        stale_inputs=list(input_payload.get("stale_inputs") or []),
        fixture_mode=data_environment in {"fixture", "test"},
        data_environment=data_environment,
    )
    prior, current, fourteen = empty_section_for(view_type)
    payload = {
        "view_id": f"view.{view_type}.{as_of_date.isoformat()}",
        "view_type": view_type,
        "as_of": as_of_date.isoformat(),
        "generated_at": str(input_payload.get("generated_at") or utc_now_iso()),
        "market_scope": market_scope,
        "horizon": _horizon_for(view_type, as_of_date),
        "mode": "analyst",
        "stance": to_plain(stance),
        "summary": str(input_payload.get("summary") or ""),
        "drivers": list(input_payload.get("drivers") or []),
        "driver_deltas": list(input_payload.get("driver_deltas") or []),
        "forecast_actual_diffs": list(input_payload.get("forecast_actual_diffs") or []),
        "prior_day_retrospective": input_payload.get("prior_day_retrospective", prior),
        "current_day_view": input_payload.get("current_day_view", current),
        "fourteen_day_outlook": input_payload.get("fourteen_day_outlook", fourteen),
        "evidence": list(input_payload.get("evidence") or []),
        "data_quality": to_plain(data_quality),
        "missing_inputs": missing_inputs,
        "source_lineage": list(input_payload.get("source_lineage") or []),
        "scenarios": list(input_payload.get("scenarios") or []),
    }
    _validate(load_yaml_unique(repo_root / "schemas" / "view.schema.json"), payload, "view")
    return payload


def validate_view_manifest(repo_root: Path, schema_dir: Path) -> dict[str, Any]:
    repo_root = Path(repo_root)
    schema_dir = Path(schema_dir)
    manifest_path = repo_root / "views" / "manifest.yaml"
    manifest = load_yaml_unique(manifest_path)
    if not isinstance(manifest, dict):
        raise WorkbenchException(VIEW_ERROR, f"View manifest must be a mapping: {manifest_path}")
    template_schema = load_yaml_unique(schema_dir / "view_template.schema.json")
    skill_ids = load_skill_ids(repo_root / "skills")
    validated: list[str] = []
    for item in manifest.get("templates") or []:
        template_path = repo_root / "views" / str(item.get("path"))
        if not template_path.exists():
            raise WorkbenchException(VIEW_ERROR, f"View template missing: {template_path}")
        template = load_yaml_unique(template_path)
        _validate(template_schema, template, str(template_path))
        for skill_id in template.get("skill_refs") or item.get("skill_refs") or []:
            if skill_id not in skill_ids:
                raise WorkbenchException(VIEW_ERROR, f"View template {template.get('id')} references unknown skill {skill_id}")
        validated.append(str(template_path))
    return {"manifest": str(manifest_path), "templates": len(validated), "validated": validated}
