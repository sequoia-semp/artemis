from __future__ import annotations

from pathlib import Path
from typing import Any

from ..agent_runtime.context_loader import collect_context
from .tickets import load_development_ticket


def collect_development_context(repo_root: Path, ticket_id: str, config_path: Path | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root)
    config_path = config_path or repo_root / "local" / "llm_config.example.yaml"
    context = collect_context(repo_root, ticket_id, config_path)
    context["mode"] = "development"
    context["artemis_config"] = "artemis.yaml"
    context["ticket"] = load_development_ticket(repo_root, ticket_id)
    return context
