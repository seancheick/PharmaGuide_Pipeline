"""F1/F3 and SINEMET source-scope regressions from the November clinical review."""

import json
from pathlib import Path

import pytest

from build_medication_depletions_artifact import build_artifact

DATA = Path(__file__).resolve().parents[1] / "data"


def _load(name):
    return json.loads((DATA / name).read_text())


def _pairs():
    return {r["id"]: r for r in _load("curated_interactions/curated_interactions_v1.json")["interactions"]}


def test_isotretinoin_vitamin_a_and_beta_carotene_have_distinct_source_scope():
    pairs = _pairs()
    vitamin = pairs["DSI_ISOTRETINOIN_VITAMIN_A"]
    beta = pairs["DSI_ISOTRETINOIN_BETA_CAROTENE"]
    assert vitamin["agent1_id"] == beta["agent1_id"] == "6064"
    assert vitamin["agent2_canonical_id"] == "vitamin_a"
    assert beta["agent2_id"] == "ref:beta_carotene"
    assert beta["agent2_canonical_id"] == "beta_carotene"
    assert vitamin["severity"] == beta["severity"] == "Major"
    assert "oral isotretinoin" in vitamin["management"].lower()
    assert "oral isotretinoin" in beta["management"].lower()
    assert "precaution" in beta["mechanism"].lower()
    assert "provitamin" in beta["mechanism"].lower()
    assert "not" in beta["mechanism"].lower() and "retinol" in beta["mechanism"].lower()
    assert "confirmation" in beta["evidence_notes"].lower()
    assert not any(r["agent1_id"] == "6064" and r.get("agent2_canonical_id") in {
        "lutein", "lycopene", "zeaxanthin", "astaxanthin"
    } for r in pairs.values())


def test_iv_zoledronic_acid_is_excluded_from_oral_absorption_class():
    row = _load("drug_classes.json")["classes"]["class:bisphosphonates"]
    assert "77655" not in row["member_rxcuis"]
    assert "zoledronic acid" not in row["member_names"]
    assert "77655" in row["excluded_member_rxcuis"]
    assert {"904952", "904954", "904955"} <= set(row["excluded_member_rxcuis"])
    assert {"904932", "904934", "904936", "904946"}.isdisjoint(row["excluded_member_rxcuis"])
    assert set(row["member_rxcuis"]) == {"46041", "115264", "73056"}
    assert "intravenous ibandronate" in row["notes"].lower()


@pytest.mark.parametrize("pair_id", ["DSI_CALCIUM_BISPHOSPHONATE", "DSI_MAGNESIUM_BISPHOSPHONATE"])
def test_bisphosphonate_mineral_copy_has_drug_specific_direction_and_form(pair_id):
    row = _pairs()[pair_id]
    assert row["severity"] == "Moderate"
    assert row["agent1_id"] == "class:bisphosphonates"
    text = row["management"].lower()
    assert "alendronate" in text and "30 minutes after" in text
    assert "ibandronate tablets" in text and "60 minutes after" in text
    assert "actonel" in text and "different time of day" in text
    assert "atelvia" in text and "after breakfast" in text
    assert "intravenous" in text
    assert "route" in row["evidence_notes"].lower()


def test_sinemet_b6_depletion_is_recorded_but_cannot_publish():
    source = _load("medication_depletions.json")
    row = next(r for r in source["depletions"] if r["id"] == "DEP_CARBIDOPA_LEVODOPA_B6")
    assert row["drug_ref"]["id"] == "103990"  # RxNorm MIN: carbidopa / levodopa, not levodopa alone.
    assert row["depleted_nutrient"]["canonical_id"] == "vitamin_b6_pyridoxine"
    assert row["citation_review_status"] == "needs_revision"
    assert row.get("b1_clinical_approval_status") != "approved_for_controlled_beta"
    assert "not established" == row["onset_timeline"]
    assert "continue" in row["recommendation"].lower()
    assert "prior" in row["monitoring_note"].lower() and "periodically" in row["monitoring_note"].lower()
    artifact = build_artifact(source, content_version="batch6-test")
    assert row["id"] in artifact["_metadata"]["withheld_entry_ids"]
    assert row["id"] not in {r["id"] for r in artifact["depletions"]}
    assert "DEP_STATINS_COQ10" in {r["id"] for r in artifact["depletions"]}  # positive control


def test_carbidopa_levodopa_has_no_blanket_supplemental_b6_warning():
    # SINEMET pharmacokinetics and B6 management expressly permit supplemental B6.
    # Source/artifact guard, not an app runtime/display assertion.
    # Check both orientations in all authored shards and every B6 profile rule.
    classes = _load("drug_classes.json")["classes"]
    identities = {"103990", "6375", "2019", "197444", "36572"}
    classes_for_sinemet = {key for key, value in classes.items() if identities.intersection(value["member_rxcuis"])}
    b6 = {"C0034283", "C0034286", "vitamin_b6_pyridoxine", "pyridoxine", "ref:vitamin_b6_pyridoxine"}
    matching = []
    for path in (DATA / "curated_interactions").glob("*.json"):
        blob = json.loads(path.read_text())
        for row in blob.get("interactions", []):
            for medicine, nutrient in (("agent1", "agent2"), ("agent2", "agent1")):
                if row.get(f"{medicine}_id") in identities | classes_for_sinemet and (
                    row.get(f"{nutrient}_id") in b6 or row.get(f"{nutrient}_canonical_id") in b6
                ):
                    matching.append(row["id"])
    assert not matching
    assert _pairs()["DSI_LEVODOPA_IRON"]["agent1_id"] == "6375"  # medicine identity remains covered
    for rule in _load("ingredient_interaction_rules.json")["interaction_rules"]:
        if rule.get("subject_ref", {}).get("canonical_id") not in b6:
            continue
        for sub in rule.get("drug_class_rules", []):
            assert "class:" + sub["drug_class_id"] not in classes_for_sinemet
