"""NAC evidence must not imply outcomes the cited human studies did not test."""

from __future__ import annotations

import json
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "backed_clinical_studies.json"


def _entry() -> dict:
    payload = json.loads(DATA_PATH.read_text())
    return next(entry for entry in payload["backed_clinical_studies"] if entry["id"] == "INGR_NAC")


def test_nac_consumer_goal_is_limited_to_supported_outcomes() -> None:
    entry = _entry()

    assert entry["health_goals_supported"] == ["Immune Support"]
    consumer_claim_surface = json.dumps({
        "goals": entry["health_goals_supported"],
        "endpoints": entry["key_endpoints"],
        "notes": entry["notes"],
        "notable_studies": entry["notable_studies"],
    }).lower()
    assert "longevity" not in consumer_claim_surface


def test_nac_removes_untraceable_aggregate_counts_and_stale_tags() -> None:
    entry = _entry()

    assert "total_enrollment" not in entry
    assert "registry_completed_trials_count" not in entry
    assert entry["published_rct_count"] == 1
    assert entry["published_meta_review_count"] == 3
    assert set(entry["endpoint_relevance_tags"]) == {
        "immune_support", "muscle_recovery", "stress_mood"
    }
    rationale = entry["effect_direction_rationale"].lower()
    assert "367" not in rationale and "2810" not in rationale
    assert "no longevity outcome" in rationale


def test_each_nac_reference_declares_its_narrow_supported_claims() -> None:
    claims = {
        ref["pmid"]: set(ref["supports_claims"])
        for ref in _entry()["references_structured"]
    }

    assert claims["9230243"] == {
        "influenza_like_symptom_attenuation",
        "cell_mediated_immunity",
        "not_infection_prevention",
    }
    assert claims["39632267"] == {
        "glutathione",
        "oxidative_stress_biomarkers",
        "exercise_recovery_biomarkers",
    }
    assert claims["31107966"] == {"chronic_bronchitis_copd_mucolytic_outcomes"}
    assert claims["29457216"] == {"condition_specific_psychiatric_adjunct_outcomes"}
