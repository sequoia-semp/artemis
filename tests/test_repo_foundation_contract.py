from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _load_jsonc(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    without_comments = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if escaped:
            without_comments.append(char)
            escaped = False
        elif char == "\\" and in_string:
            without_comments.append(char)
            escaped = True
        elif char == '"':
            without_comments.append(char)
            in_string = not in_string
        elif not in_string and char == "/" and next_char == "/":
            while index < len(text) and text[index] != "\n":
                index += 1
            without_comments.append("\n")
        else:
            without_comments.append(char)
        index += 1
    return json.loads("".join(without_comments))


def test_root_markdown_allowlist():
    allowed = {"README.md", "AGENTS.md"}
    found = {path.name for path in ROOT.glob("*.md")}
    assert found <= allowed


def test_root_planning_files_are_archived():
    assert not (ROOT / "pjm_workbench_mvp_agent_spec.md").exists()
    assert not (ROOT / "pjm_workbench_mvp_backlog.yaml").exists()
    assert (ROOT / "docs/archive/pjm_workbench_mvp_agent_spec.md").exists()
    assert (ROOT / "work/backlog/pjm_workbench_mvp_backlog.yaml").exists()


def test_product_entrypoints_have_no_individual_convention_math():
    forbidden = ["0.25/d", "2,500 MMBtu/day", "Do not revert", "1.0/d = 4", "WH/AD", "FIRST/SECOND"]
    for relative_path in ["README.md", "AGENTS.md", "llms.txt"]:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        for item in forbidden:
            assert item not in text


def test_llms_txt_is_navigation_not_policy():
    text = (ROOT / "llms.txt").read_text(encoding="utf-8")
    assert "artemis.yaml" in text
    assert "docs/README.md" in text
    assert "pjm_workbench_mvp_agent_spec.md" not in text
    assert "pjm_workbench_mvp_backlog.yaml" not in text


def test_agents_has_general_convention_rule_not_specific_math():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "locked market conventions" in text
    assert "approved change request" in text


def test_legacy_llm_config_is_absent_or_stub():
    path = ROOT / "local/llm_config.example.yaml"
    if path.exists():
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        assert payload.get("legacy") is True
        assert "profiles" not in payload
        assert "context" not in payload
        assert "safety" not in payload


def test_make_validate_includes_artemis_validators():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "validate-artemis" in text
    assert "$(ARTEMIS) config validate" in text
    assert "$(ARTEMIS) skill validate" in text
    assert "$(ARTEMIS) views validate" in text
    assert "$(ARTEMIS) data-sources validate" in text
    assert "$(ARTEMIS) capabilities" in text


def test_integration_descriptors_non_authoritative():
    for path in (ROOT / "integrations").rglob("*.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(payload, dict) and "authoritative" in payload:
            assert payload["authoritative"] is False


def test_root_opencode_is_minimal_permissions_shim():
    config = _load_jsonc(ROOT / "opencode.jsonc")
    assert "permission" in config
    assert "model" not in config
    assert "provider" not in config
    assert config["permission"]["edit"] == "ask"
