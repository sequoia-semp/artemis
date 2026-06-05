from __future__ import annotations

from pathlib import Path

from pga_workbench.dev.release import build_release_candidate


ROOT = Path(__file__).resolve().parents[1]


def test_release_candidate_schema_validates():
    candidate = build_release_candidate(ROOT, "T-0018")

    assert candidate["id"] == "RC-0.2.0-T-0018"
    assert candidate["source_branch"]
    assert candidate["package_version"] == "0.2.0"
    assert "artemis capabilities" in candidate["validation_commands"]
    assert candidate["validation_skipped"] is True
    assert candidate["validation_passed"] is False
    assert candidate["ready_for_release_prep"] is False
    assert candidate["validation"]["python -m pytest -q"]["status"] == "skipped"
    assert candidate["manifest_hashes"]["artemis.yaml"]
    assert candidate["manifest_hashes"]["schemas/state_pack.schema.json"]
    assert candidate["manifest_hashes"]["schemas/forward_price_heatmap.schema.json"]
    assert candidate["requires_human_review"] is True
    assert candidate["approved"] is False
