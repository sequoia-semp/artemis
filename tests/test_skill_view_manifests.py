from __future__ import annotations

from pathlib import Path

from pga_workbench.analyst.view_engine import validate_view_manifest
from pga_workbench.skills.validator import validate_skill_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_skill_manifest_validates_and_references_registered_tools():
    result = validate_skill_manifest(ROOT, ROOT / "schemas")

    assert result["skills"] == 7
    assert result["procedural_skills"] == 10


def test_view_manifest_validates_and_references_registered_skills():
    result = validate_view_manifest(ROOT, ROOT / "schemas")

    assert result["templates"] == 6
