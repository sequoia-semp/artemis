from __future__ import annotations

from pathlib import Path
from typing import Any

from ..agent_runtime.work_item_loader import load_ticket


def load_development_ticket(repo_root: Path, ticket_id: str) -> dict[str, Any]:
    return load_ticket(Path(repo_root) / "work", ticket_id)
