from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.agent_runtime.native_loop import NATIVE_LOOP_ERROR, run_native_agent_loop
from pga_workbench.exceptions import WorkbenchException


def test_manual_loop_dry_run_creates_context_and_report(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("pga_workbench.agent_runtime.native_loop.load_ticket", lambda root, ticket_id: {"id": ticket_id, "status": "active"})
    monkeypatch.setattr("pga_workbench.agent_runtime.native_loop.load_coding_backend_descriptors", lambda root: {"human": {"permissions": {"forbidden": []}}})
    monkeypatch.setattr("pga_workbench.agent_runtime.native_loop.collect_development_context", lambda repo_root, ticket_id: {"ticket": {"id": ticket_id}})

    report = run_native_agent_loop(tmp_path, "T-TEST", backend="manual", dry_run=True)

    assert report["backend"] == "manual"
    assert Path(report["context_path"]).exists()
    assert (tmp_path / "development" / "agent_runs" / "T-TEST" / "latest.json").exists()
    assert report["validation_report"] is None


def test_loop_refuses_non_active_ticket(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("pga_workbench.agent_runtime.native_loop.load_ticket", lambda root, ticket_id: {"id": ticket_id, "status": "validated"})

    with pytest.raises(WorkbenchException) as exc:
        run_native_agent_loop(tmp_path, "T-TEST", backend="manual", dry_run=True)

    assert exc.value.code == NATIVE_LOOP_ERROR


def test_forbidden_backend_command_is_rejected(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("pga_workbench.agent_runtime.native_loop.load_ticket", lambda root, ticket_id: {"id": ticket_id, "status": "active"})
    monkeypatch.setattr(
        "pga_workbench.agent_runtime.native_loop.load_coding_backend_descriptors",
        lambda root: {"opencode": {"permissions": {"forbidden": ["opencode run"]}}},
    )
    monkeypatch.setattr("pga_workbench.agent_runtime.native_loop.collect_development_context", lambda repo_root, ticket_id: {"ticket": {"id": ticket_id}})

    with pytest.raises(WorkbenchException):
        run_native_agent_loop(tmp_path, "T-TEST", backend="opencode", dry_run=True)
