"""Entered medicines reach the interaction-rule classes meant for them, and only those.

The app turns each `class:x` in drug_classes.json into the rule class `x`
(MedicationClassBridge.profileGateIdsForClasses), and the only other crosswalk
is antiplatelet_agents -> antiplatelets. Each case pairs intended members with
exclusions, so a broader class cannot pass by reaching "at least one" drug.
RxCUIs were content-verified against RxNorm (ingredient, active) on 2026-11-11.
Interaction audit Stage 2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
APP_PROFILE_GATE_OVERRIDES = {"class:antiplatelet_agents": "antiplatelets"}


def _load(name: str):
    return json.loads((DATA / name).read_text())


def rule_classes_for(rxcui: str) -> set[str]:
    return {
        APP_PROFILE_GATE_OVERRIDES.get(cid, cid.removeprefix("class:"))
        for cid, c in _load("drug_classes.json")["classes"].items()
        if rxcui in c["member_rxcuis"] and rxcui not in c.get("excluded_member_rxcuis", [])
    }


def sub_rule_gate(rule_id: str, drug_class_id: str) -> set[str]:
    rule = next(r for r in _load("ingredient_interaction_rules.json")["interaction_rules"] if r["id"] == rule_id)
    sub = next(d for d in rule["drug_class_rules"] if d["drug_class_id"] == drug_class_id)
    return set(sub["profile_gate"]["requires"]["drug_classes_any"])


HYPOGLYCEMIC_TIERS = {"hypoglycemics_high_risk", "hypoglycemics_lower_risk", "hypoglycemics_unknown"}

MEMBERSHIP = [
    # (rule class, intended members, exclusions)
    ("cardiac_glycosides", {"digoxin": "3407", "digitoxin": "3403"}, {"amiodarone": "703"}),
    (
        "thyroid_medications",
        {"levothyroxine": "10582", "liothyronine": "10814", "thyroid (USP)": "10572"},
        # Every thyroid rule concerns thyroid-hormone absorption or action;
        # antithyroid drugs are a different treatment.
        {"methimazole": "6835", "propylthiouracil": "8794"},
    ),
    (
        "antidepressants_ssri_snri",
        {"sertraline": "36437", "venlafaxine": "39786", "duloxetine": "72625", "desvenlafaxine": "734064"},
        {"bupropion": "42347", "amitriptyline": "704"},
    ),
    (
        "anticholinergics",
        {"oxybutynin": "32675", "benztropine": "1424", "hyoscyamine": "153970"},
        # Beta-3 agonists share ATC G04BD but are not antimuscarinic.
        # Diphenhydramine and amitriptyline await PharmD review.
        {"mirabegron": "1300786", "vibegron": "2472254", "diphenhydramine": "3498", "amitriptyline": "704"},
    ),
    (
        "hypoglycemics_high_risk",
        {"insulin glargine": "274783", "glipizide": "4821", "repaglinide": "73044"},
        {"metformin": "6809", "pioglitazone": "33738", "guar gum": "26344"},
    ),
    (
        "hypoglycemics_lower_risk",
        {"metformin": "6809", "semaglutide": "1991302", "empagliflozin": "1545653", "sitagliptin": "593411"},
        {"glipizide": "4821", "tirzepatide": "2601723", "guar gum": "26344"},
    ),
    (
        "hypoglycemics_unknown",
        # Diabetes medicines the signed vocabulary names in neither tier take
        # the conservative tier (its severities equal the high-risk tier's).
        {"pioglitazone": "33738", "tirzepatide": "2601723", "pramlintide": "139953", "acarbose": "16681"},
        {"metformin": "6809", "insulin glargine": "274783", "guar gum": "26344"},
    ),
]


@pytest.mark.parametrize("rule_class,members,exclusions", MEMBERSHIP, ids=[m[0] for m in MEMBERSHIP])
def test_rule_class_membership(rule_class, members, exclusions):
    missing = {name for name, rxcui in members.items() if rule_class not in rule_classes_for(rxcui)}
    wrongly = {name for name, rxcui in exclusions.items() if rule_class in rule_classes_for(rxcui)}
    assert not missing, f"{rule_class} misses {sorted(missing)}"
    assert not wrongly, f"{rule_class} wrongly includes {sorted(wrongly)}"


def test_each_diabetes_medicine_sits_in_exactly_one_tier():
    for rxcui in ["274783", "4821", "73044", "6809", "1991302", "1545653", "593411", "33738", "2601723", "139953", "16681"]:
        assert len(rule_classes_for(rxcui) & HYPOGLYCEMIC_TIERS) == 1, rxcui


def test_guar_gum_is_not_a_diabetes_medicine():
    assert not rule_classes_for("26344") & HYPOGLYCEMIC_TIERS


@pytest.mark.parametrize("name,rxcui", [("clobazam", "21241"), ("valproic acid", "11118"), ("levetiracetam", "114477")])
def test_cbd_antiseizure_rule_reaches_named_seizure_medicines(name, rxcui):
    assert rule_classes_for(rxcui) & sub_rule_gate("RULE_BANNED_CBD_INTERACTIONS", "anticonvulsants"), name


def test_cbd_antiseizure_rule_does_not_reach_other_benzodiazepines():
    assert not rule_classes_for("596") & sub_rule_gate("RULE_BANNED_CBD_INTERACTIONS", "anticonvulsants")


def test_valproate_stays_out_of_the_enzyme_inducer_anticonvulsant_class():
    """The anticonvulsant-contraceptive pair speaks of enzyme induction."""
    assert "anticonvulsants" not in rule_classes_for("11118")


@pytest.mark.parametrize("name,rxcui", [("venlafaxine", "39786"), ("duloxetine", "72625"), ("sertraline", "36437")])
def test_st_johns_wort_antidepressant_rule_reaches_ssris_and_snris(name, rxcui):
    assert rule_classes_for(rxcui) & sub_rule_gate("RULE_INGREDIENT_ST_JOHNS_WORT", "antidepressants_ssri_snri"), name
