from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _load_jsonc(path: Path):
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


def test_root_opencode_config_is_permissions_only_shim():
    path = ROOT / "opencode.jsonc"
    text = path.read_text(encoding="utf-8")
    config = _load_jsonc(path)
    bash = config["permission"]["bash"]

    assert "Compatibility shim only" in text
    assert "AGENTS.md plus artemis.yaml" in text
    assert "model" not in config
    assert "provider" not in config
    assert config["permission"]["edit"] == "ask"
    assert bash["*"] == "ask"
    assert bash["git push*"] == "ask"
    assert bash["git tag*"] == "ask"
    assert bash["pga build-state-pack*"] == "ask"
    assert bash["pga normalize-*"] == "ask"
    assert bash["pga run-*"] == "ask"


def test_optional_backend_provider_orchestrator_examples_live_under_descriptor_dirs():
    assert (ROOT / "integrations/coding_backends/opencode/opencode.ollama.example.jsonc").exists()
    assert (ROOT / "integrations/coding_backends/opencode/opencode.external-model.example.jsonc").exists()
    assert (ROOT / "integrations/providers/ollama_model_profiles.legacy.yaml").exists()
    assert (ROOT / "integrations/orchestrators/openclaw_tools.readonly.yaml").exists()


def test_openclaw_manifest_is_readonly_and_blocks_publish():
    manifest = yaml.safe_load((ROOT / "integrations/orchestrators/openclaw_tools.readonly.yaml").read_text(encoding="utf-8"))
    assert manifest["mode"] == "readonly"
    tools = manifest["tools"]
    allowed_commands = [item.get("command", "") for item in tools.values() if item.get("allowed") is True]
    assert all("build-state-pack --publish" not in command for command in allowed_commands)
    assert tools["artemis_publish_state_pack"]["command"] == "pga build-state-pack --publish"
    assert tools["artemis_publish_state_pack"]["allowed"] is False
    assert tools["git_push"]["allowed"] is False
    assert tools["git_tag"]["allowed"] is False


def test_capability_registry_marks_wrappers_non_authoritative():
    registry = yaml.safe_load((ROOT / "integrations/capability_registry.yaml").read_text(encoding="utf-8"))
    for wrapper in registry["wrappers"].values():
        assert wrapper["required"] is False
        assert wrapper["authoritative"] is False
    assert "pga build-state-pack --publish" in registry["wrappers"]["openclaw"]["forbidden_commands"]
