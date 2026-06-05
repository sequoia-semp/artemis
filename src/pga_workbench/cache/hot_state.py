from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from ..serialization import read_json
from ..state.packs import validate_state_pack

HOT_STATE_INVALID = "HOT_STATE_INVALID"


class HotState:
    """Read-only view over the accepted state referenced by current.json."""

    def __init__(self, state_root: Path):
        self.state_root = Path(state_root)

    def current_pointer(self) -> dict[str, Any]:
        return read_json(self.state_root / "current.json")

    def load_current(self) -> dict[str, Any]:
        pointer = self.current_pointer()
        accepted_dir = Path(pointer["path"])
        if not accepted_dir.is_absolute():
            accepted_dir = self.state_root / accepted_dir
        if accepted_dir.parent.name != "accepted":
            raise WorkbenchException(HOT_STATE_INVALID, f"current.json must point to an accepted state: {accepted_dir}")
        validate_state_pack(accepted_dir)
        payload = read_json(accepted_dir / "state_pack.json")
        if payload["state_id"] != pointer.get("state_id"):
            raise WorkbenchException(HOT_STATE_INVALID, "current.json state_id does not match accepted state pack")
        return payload

    def artifacts(self) -> dict[str, Any]:
        return dict(self.load_current().get("artifacts", {}))
