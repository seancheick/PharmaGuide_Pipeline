import json
from pathlib import Path


DATA = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "curated_interactions"
    / "curated_interactions_v1.json"
)
BY_ID = {
    row["id"]: row for row in json.loads(DATA.read_text())["interactions"]
}


def test_disease_or_nutrient_associations_do_not_ship_as_interactions():
    rejected = {
        "DSI_DM_VITD",
        "DSI_DM_MAGNESIUM",
        "SSI_MAGNESIUM_CALCIUM",
        "SSI_VITE_VITK",
    }

    assert rejected.isdisjoint(BY_ID), (
        "Disease associations, unsupported ratio advice, and the duplicate "
        "vitamin E/vitamin K supplement warning must not ship as interactions"
    )


def test_warfarin_vitamin_e_guidance_does_not_claim_a_safe_cutoff():
    rule = BY_ID["DSI_WAR_VITE"]
    mechanism = rule["mechanism"].lower()
    management = rule["management"].lower()

    assert rule["agent1_id"] == "11289"
    assert rule["source_pmids"] == ["24166490"]
    assert "generally safe" not in management
    assert "≤400" not in management
    assert "<=400" not in management
    assert "elevate inr" not in mechanism
    assert "do not change warfarin" in management
    assert "anticoagulation" in management
