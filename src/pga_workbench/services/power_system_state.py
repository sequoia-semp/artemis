from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.time import utc_now_iso
from ..exceptions import WorkbenchException
from ..models import RunManifest
from ..state.packs import build_candidate_state_pack
from .power_system_ingestion import BUNDLE_METADATA_KEY, validate_power_system_artifact_bundle

POWER_SYSTEM_STATE_ERROR = "POWER_SYSTEM_STATE_ERROR"


def stage_power_system_bundle_candidate(
    bundle: dict[str, Any],
    state_root: Path,
    state_id: str,
    *,
    as_of: str | None = None,
    input_path: str | None = None,
    synthetic: bool = False,
) -> dict[str, Any]:
    validate_power_system_artifact_bundle(bundle)
    metadata = dict(bundle.get(BUNDLE_METADATA_KEY) or {})
    candidate_as_of = as_of or metadata.get("as_of")
    if not candidate_as_of:
        raise WorkbenchException(POWER_SYSTEM_STATE_ERROR, "State candidate as_of is required when bundle metadata does not provide one")
    manifest = RunManifest(
        run_id=state_id,
        created_at=utc_now_iso(),
        agent_pack_version="0.1.0",
        inputs=[{"path": input_path, "artifact": BUNDLE_METADATA_KEY}] if input_path else [{"artifact": BUNDLE_METADATA_KEY}],
    )
    candidate_dir = build_candidate_state_pack(Path(state_root), state_id, str(candidate_as_of), bundle, manifest, synthetic=synthetic)
    return {
        "state_id": state_id,
        "candidate_path": str(candidate_dir),
        "as_of": str(candidate_as_of),
        "synthetic": synthetic,
        "published": False,
        "composition_product_keys": list(metadata.get("composition_product_keys") or []),
    }
