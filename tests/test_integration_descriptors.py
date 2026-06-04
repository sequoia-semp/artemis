from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_artemis_referenced_integration_descriptors_exist_and_are_not_authoritative():
    config = yaml.safe_load((ROOT / "artemis.yaml").read_text(encoding="utf-8"))
    descriptor_paths = []
    for profile in (config.get("providers") or {}).get("profiles", {}).values():
        if "descriptor" in profile:
            descriptor_paths.append(profile["descriptor"])
    for backend in ((config.get("backends") or {}).get("coding") or {}).get("options", {}).values():
        descriptor_paths.append(backend["descriptor"])
    for orchestrator in (config.get("orchestrators") or {}).values():
        descriptor_paths.append(orchestrator["descriptor"])

    assert descriptor_paths
    for relative_path in descriptor_paths:
        path = ROOT / relative_path
        assert path.exists(), relative_path
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert payload["required"] is False
        assert payload["authoritative"] is False


def test_integration_readme_uses_descriptor_directories():
    text = (ROOT / "integrations/README.md").read_text(encoding="utf-8")
    assert "integrations/providers/" in text
    assert "integrations/coding_backends/" in text
    assert "integrations/orchestrators/" in text
    assert "Compatibility examples" in text
