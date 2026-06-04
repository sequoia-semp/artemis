from __future__ import annotations

from pathlib import Path

from pga_workbench.agent_runtime.kb_validator import validate_knowledge_base


ROOT = Path(__file__).resolve().parents[1]


def test_knowledge_base_scaffold_declares_advisory_authority():
    readme = (ROOT / "knowledge_base/README.md").read_text(encoding="utf-8")
    assert "advisory unless linked" in readme
    assert "cannot override" in readme
    assert "docs/CONVENTIONS_LOCKED_v0.1.md" in readme


def test_validate_knowledge_base_manifest():
    result = validate_knowledge_base(ROOT / "knowledge_base", ROOT / "schemas")
    assert result["entries"] == 4
