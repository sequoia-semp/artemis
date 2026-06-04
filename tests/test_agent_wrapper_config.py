from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_root_opencode_config_keeps_permissions_conservative():
    text = (ROOT / "opencode.jsonc").read_text(encoding="utf-8")
    assert "OpenCode is optional" in text
    assert '"edit": "ask"' in text
    assert '"*": "ask"' in text
    assert '"git push*": "ask"' in text
    assert '"git tag*": "ask"' in text
    assert "enabled_providers" not in text


def test_wrapper_docs_and_examples_exist():
    assert (ROOT / "docs/WRAPPER_ABSTRACTION_POLICY.md").exists()
    assert (ROOT / "docs/AGENT_MODES.md").exists()
    assert (ROOT / "integrations/opencode/opencode.ollama.example.jsonc").exists()
    assert (ROOT / "integrations/opencode/opencode.external-model.example.jsonc").exists()


def test_openclaw_manifest_is_readonly_and_blocks_publish():
    manifest = yaml.safe_load((ROOT / "integrations/openclaw/artemis_tools.readonly.yaml").read_text(encoding="utf-8"))
    assert manifest["mode"] == "readonly"
    allowed_commands = [
        item.get("command_template", "")
        for item in manifest["allowed_tools"].values()
    ]
    assert all("build-state-pack --publish" not in command for command in allowed_commands)
    forbidden_commands = [
        item.get("command_template", "")
        for item in manifest["forbidden_tools"].values()
    ]
    assert "pga build-state-pack --publish" in forbidden_commands
