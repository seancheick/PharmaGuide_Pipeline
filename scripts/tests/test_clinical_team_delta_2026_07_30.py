"""Clinical-team review delta locks for 2026-07-30.

These tests pin the authored source that generates both the reviewed
medication-nutrient artifact and the packaged interaction database.
"""

from __future__ import annotations

import json
from pathlib import Path


DATA = Path(__file__).parents[1] / "data"
MED_MED = DATA / "curated_interactions" / "med_med_pairs_v1.json"


def _med_med_by_id() -> dict[str, dict]:
    payload = json.loads(MED_MED.read_text(encoding="utf-8"))
    return {row["id"]: row for row in payload["interactions"]}


def test_cholestyramine_warfarin_is_an_authored_direct_drug_pair():
    pair = _med_med_by_id()["DDI_CHOLESTYRAMINE_WARFARIN"]

    assert pair["type"] == "Med-Med"
    assert pair["agent1_id"] == "2447"
    assert pair["agent2_id"] == "11289"
    assert pair["severity"] == "Major"
    assert pair["direction"] == "harmful"
    assert pair["materiality"] == "presence"
    assert pair["evidence_basis"] == "label_regulatory"
    assert pair["clinical_confidence"] == "high"
    assert any(
        "09420793-7357-4194-8172-0b1cddb167fe" in url
        for url in pair["source_urls"]
    )


def test_cholestyramine_warfarin_copy_preserves_label_timing_and_change_control():
    pair = _med_med_by_id()["DDI_CHOLESTYRAMINE_WARFARIN"]
    management = pair["management"].lower()
    mechanism = pair["mechanism"].lower()

    assert "reduce the absorption of warfarin" in mechanism
    assert "at least 1 hour before" in management
    assert "4 to 6 hours after" in management
    assert "keep" in management and "timing consistent" in management
    assert "starting, stopping, or changing" in management
    assert "do not change warfarin on your own" in management
