"""Clinical-team review delta locks for 2026-07-30.

These tests pin the authored source that generates both the reviewed
medication-nutrient artifact and the packaged interaction database.
"""

from __future__ import annotations

import json
from pathlib import Path


DATA = Path(__file__).parents[1] / "data"
MED_MED = DATA / "curated_interactions" / "med_med_pairs_v1.json"
MEDICATION_DEPLETIONS = DATA / "medication_depletions.json"
CLINICAL_TEAM_DELTA_IDS = {
    "DEP_ANTACIDS_IRON",
    "DEP_DIURETICS_THIAMINE",
    "DEP_SSRIS_SODIUM",
    "DEP_LEVOTHYROXINE_CALCIUM",
    "DEP_LEVOTHYROXINE_IRON",
    "DEP_ANTICOAGULANTS_VITAMINK",
    "DEP_ORLISTAT_VITAMINA",
    "DEP_CHOLESTYRAMINE_VITAMINA",
    "DEP_CHOLESTYRAMINE_VITAMIND",
    "DEP_CHOLESTYRAMINE_VITAMINE",
    "DEP_CHOLESTYRAMINE_VITAMINK",
}


def _med_med_by_id() -> dict[str, dict]:
    payload = json.loads(MED_MED.read_text(encoding="utf-8"))
    return {row["id"]: row for row in payload["interactions"]}


def _depletions_by_id() -> dict[str, dict]:
    payload = json.loads(MEDICATION_DEPLETIONS.read_text(encoding="utf-8"))
    return {row["id"]: row for row in payload["depletions"]}


def test_delta_records_name_the_clinical_reviewer_without_erasing_ai_audit():
    records = _depletions_by_id()
    assert CLINICAL_TEAM_DELTA_IDS <= records.keys()

    for record_id in CLINICAL_TEAM_DELTA_IDS:
        record = records[record_id]
        assert record["reviewed_at"] == "2026-07-30"
        assert record["reviewer"] == "PharmaGuide Clinical Team"
        assert record["b1_evidence_auditor"] == "openai_codex_ai_clinical_audit"


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
