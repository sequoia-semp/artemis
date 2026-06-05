from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any

from jsonschema import Draft202012Validator

from ..core.time import utc_now_iso
from ..exceptions import WorkbenchException
from ..models import MorningStatePack, RunManifest
from ..registry import SHARED_READONLY_PUBLISH_BLOCKED, SYNTHETIC_PROMOTION_BLOCKED
from ..serialization import read_json, write_json

STATE_PACK_INVALID = "STATE_PACK_INVALID"
SCHEMA_ROOT = Path(__file__).resolve().parents[3] / "schemas"


def build_candidate_state_pack(root: Path, state_id: str, as_of: str, artifacts: dict, manifest: RunManifest, synthetic: bool = False) -> Path:
    candidate_dir = Path(root) / "candidates" / state_id
    if candidate_dir.exists():
        raise WorkbenchException("STATE_CANDIDATE_EXISTS", f"Candidate already exists: {state_id}")
    candidate_dir.mkdir(parents=True)
    pack = MorningStatePack(
        state_id=state_id,
        as_of=as_of,
        created_at=utc_now_iso(),
        synthetic=synthetic,
        artifacts=artifacts,
        manifest=manifest,
    )
    write_json(candidate_dir / "state_pack.json", pack)
    validate_state_pack(candidate_dir)
    return candidate_dir


def validate_state_pack(candidate_dir: Path) -> None:
    candidate_dir = Path(candidate_dir)
    payload = read_json(candidate_dir / "state_pack.json")
    _validate_state_pack_schema(payload)
    state_id = str(payload["state_id"])
    if candidate_dir.name != state_id:
        raise WorkbenchException(STATE_PACK_INVALID, f"State pack directory/id mismatch: {candidate_dir.name} != {state_id}")
    _parse_utc_timestamp(str(payload["as_of"]), "as_of")
    _parse_utc_timestamp(str(payload["created_at"]), "created_at")
    manifest = payload["manifest"]
    if str(manifest["run_id"]) != state_id:
        raise WorkbenchException(STATE_PACK_INVALID, f"State pack manifest run_id mismatch: {manifest['run_id']} != {state_id}")
    _parse_utc_timestamp(str(manifest["created_at"]), "manifest.created_at")
    _validate_delivery_windows(payload.get("artifacts") or {})


def _validate_state_pack_schema(payload: dict[str, Any]) -> None:
    schema = read_json(SCHEMA_ROOT / "state_pack.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(STATE_PACK_INVALID, f"state_pack.json{suffix}: {first.message}")


def _parse_utc_timestamp(value: str, label: str) -> datetime:
    if not value.endswith("Z"):
        raise WorkbenchException(STATE_PACK_INVALID, f"{label} must be UTC with Z suffix: {value}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkbenchException(STATE_PACK_INVALID, f"{label} is not a valid ISO timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise WorkbenchException(STATE_PACK_INVALID, f"{label} must be UTC: {value}")
    return parsed


def _walk_artifact_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        records.append(value)
        for child in value.values():
            records.extend(_walk_artifact_records(child))
    elif isinstance(value, list):
        for child in value:
            records.extend(_walk_artifact_records(child))
    return records


def _validate_delivery_windows(artifacts: dict[str, Any]) -> None:
    for record in _walk_artifact_records(artifacts):
        has_start = "delivery_start" in record
        has_end = "delivery_end" in record
        if not has_start and not has_end:
            continue
        if not has_start or not has_end:
            raise WorkbenchException(STATE_PACK_INVALID, "delivery_start and delivery_end must be present together")
        start = _parse_utc_timestamp(str(record["delivery_start"]), "delivery_start")
        end = _parse_utc_timestamp(str(record["delivery_end"]), "delivery_end")
        if start >= end:
            raise WorkbenchException(STATE_PACK_INVALID, "delivery_start must be before delivery_end")


def publish_candidate_state_pack(root: Path, state_id: str, shared_readonly: bool = False) -> Path:
    if shared_readonly:
        raise WorkbenchException(SHARED_READONLY_PUBLISH_BLOCKED, "shared-readonly mode cannot publish shared state")
    root = Path(root)
    candidate_dir = root / "candidates" / state_id
    validate_state_pack(candidate_dir)
    payload = read_json(candidate_dir / "state_pack.json")
    if payload.get("synthetic") is True:
        raise WorkbenchException(SYNTHETIC_PROMOTION_BLOCKED, "Synthetic state packs cannot be promoted")
    accepted_dir = root / "accepted" / state_id
    if accepted_dir.exists():
        raise WorkbenchException("STATE_ALREADY_ACCEPTED", f"Accepted state already exists: {state_id}")
    accepted_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(candidate_dir), str(accepted_dir))
    pointer = {"state_id": state_id, "path": str(accepted_dir), "updated_at": utc_now_iso()}
    write_json(root / "current.json.tmp", pointer)
    (root / "current.json.tmp").replace(root / "current.json")
    return accepted_dir
