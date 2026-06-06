from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.analyst.view_engine import validate_view_manifest
from pga_workbench.registry import load_yaml_unique
from pga_workbench.skills.validator import validate_skill_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_skill_manifest_validates_and_references_registered_tools():
    result = validate_skill_manifest(ROOT, ROOT / "schemas")

    assert result["skills"] == 8
    assert result["procedural_skills"] == 10
    assert str(ROOT / "skills" / "analyst" / "audit_power_system_sources.yaml") in result["validated"]


def test_source_audit_analyst_skill_uses_read_only_audit_tool():
    descriptor = load_yaml_unique(ROOT / "skills" / "analyst" / "audit_power_system_sources.yaml")

    assert descriptor["id"] == "analyst.audit_power_system_sources"
    assert descriptor["tools"] == ["power_system_source_audit"]
    assert descriptor["outputs"] == ["power_system_source_audit"]
    assert descriptor["validation"]["schemas"] == ["schemas/power_system_source_audit.schema.json"]
    assert "approve_source_publications" in descriptor["llm_role"]["forbidden"]


def test_view_manifest_validates_and_references_registered_skills():
    result = validate_view_manifest(ROOT, ROOT / "schemas")

    assert result["templates"] == 6


def _copy_skill_validation_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "skills", repo / "skills")
    shutil.copytree(ROOT / ".agents", repo / ".agents")
    (repo / "registries").mkdir()
    shutil.copy2(ROOT / "registries" / "tools.yaml", repo / "registries" / "tools.yaml")
    shutil.copytree(ROOT / "schemas", repo / "schemas")
    return repo


def test_skill_validation_rejects_unmanifested_shim(tmp_path: Path):
    repo = _copy_skill_validation_repo(tmp_path)
    extra = repo / ".agents" / "skills" / "unmanifested" / "SKILL.md"
    extra.parent.mkdir(parents=True)
    extra.write_text(
        "---\nmetadata:\n  canonical: skills/period_parsing/SKILL.md\n---\nLoad canonical skill.\n",
        encoding="utf-8",
    )

    with pytest.raises(WorkbenchException) as exc:
        validate_skill_manifest(repo, repo / "schemas")
    assert "Unmanifested active skill shims" in exc.value.message


def test_skill_validation_rejects_missing_canonical_pointer(tmp_path: Path):
    repo = _copy_skill_validation_repo(tmp_path)
    shim = repo / ".agents" / "skills" / "period-parsing" / "SKILL.md"
    shim.write_text(shim.read_text(encoding="utf-8").replace("skills/period_parsing/SKILL.md", "skills/missing/SKILL.md"), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_skill_manifest(repo, repo / "schemas")
    assert "shim canonical mismatch" in exc.value.message


def test_skill_validation_rejects_shim_domain_rules(tmp_path: Path):
    repo = _copy_skill_validation_repo(tmp_path)
    shim = repo / ".agents" / "skills" / "period-parsing" / "SKILL.md"
    shim.write_text(shim.read_text(encoding="utf-8") + "\nBasis orientation is first minus second.\n", encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_skill_manifest(repo, repo / "schemas")
    assert "shim restates domain authority" in exc.value.message
