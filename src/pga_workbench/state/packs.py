from __future__ import annotations

from pathlib import Path
import shutil

from ..core.time import utc_now_iso
from ..exceptions import WorkbenchException
from ..models import MorningStatePack, RunManifest
from ..registry import SHARED_READONLY_PUBLISH_BLOCKED, SYNTHETIC_PROMOTION_BLOCKED
from ..serialization import read_json, write_json


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
    payload = read_json(Path(candidate_dir) / "state_pack.json")
    required = {"state_id", "as_of", "created_at", "synthetic", "artifacts", "manifest"}
    missing = required - set(payload)
    if missing:
        raise WorkbenchException("STATE_PACK_INVALID", f"State pack missing fields: {sorted(missing)}")


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
