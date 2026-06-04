from __future__ import annotations

from pathlib import Path
from typing import Any

from ..serialization import read_json


class HotState:
    """Read-only view over the accepted state referenced by current.json."""

    def __init__(self, state_root: Path):
        self.state_root = Path(state_root)

    def current_pointer(self) -> dict[str, Any]:
        return read_json(self.state_root / "current.json")

    def load_current(self) -> dict[str, Any]:
        pointer = self.current_pointer()
        return read_json(Path(pointer["path"]) / "state_pack.json")

    def artifacts(self) -> dict[str, Any]:
        return dict(self.load_current().get("artifacts", {}))
