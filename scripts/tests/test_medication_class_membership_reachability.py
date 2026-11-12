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
        # Dr. Pham D2 (2026-11-11): diphenhydramine joins, and each tricyclic whose
        # own label identifies anticholinergic properties (labels read 2026-11-11).
        {
            "oxybutynin": "32675", "benztropine": "1424", "hyoscyamine": "153970",
            "diphenhydramine": "3498", "amitriptyline": "704", "nortriptyline": "7531",
            "imipramine": "5691", "desipramine": "3247", "clomipramine": "2597",
            "doxepin": "3638", "protriptyline": "8886", "trimipramine": "10834", "amoxapine": "722",
        },
        # Beta-3 agonists share ATC G04BD but are not antimuscarinic; membership
        # does not extend to all antihistamines or antidepressants (D2);
        # maprotiline has no current DailyMed label to review.
        {
            "mirabegron": "1300786", "vibegron": "2472254", "loratadine": "28889", "cetirizine": "20610",
            "fexofenadine": "87636", "sertraline": "36437", "fluoxetine": "4493", "maprotiline": "6646",
            # First-generation antihistamines in sleep and cold products stay out too.
            "doxylamine": "3642", "chlorpheniramine": "2400", "hydroxyzine": "5553",
        },
    ),
    (
        "hypoglycemics_high_risk",
        {"insulin glargine": "274783", "glipizide": "4821", "repaglinide": "73044"},
        {"metformin": "6809", "pioglitazone": "33738", "guar gum": "26344"},
    ),
    (
        "hypoglycemics_lower_risk",
        # Dr. Pham D3: tirzepatide carries lower intrinsic risk alone (MOUNJARO 5.3).
        {
            "metformin": "6809", "semaglutide": "1991302", "empagliflozin": "1545653",
            "sitagliptin": "593411", "tirzepatide": "2601723",
        },
        {"glipizide": "4821", "pramlintide": "139953", "guar gum": "26344"},
    ),
    (
        "hypoglycemics_unknown",
        # Diabetes medicines the signed vocabulary names in neither tier take
        # the conservative tier (its severities equal the high-risk tier's).
        # Pramlintide stays here (D3): it is used with mealtime insulin, so
        # without insulin entered the regimen is incomplete, not low risk.
        {"pioglitazone": "33738", "pramlintide": "139953", "acarbose": "16681"},
        {"metformin": "6809", "insulin glargine": "274783", "guar gum": "26344", "tirzepatide": "2601723"},
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


SEVERITY_RANK = {"monitor": 1, "caution": 2, "avoid": 3, "contraindicated": 4}


def strongest_severity(rule_id: str, rxcuis: list[str]) -> str | None:
    """The strongest severity among a rule's drug-class sub-rules whose `requires` a medication list reaches.

    This proves the medication-class branch only. It ignores `excludes`, condition and profile-flag gates, dose
    gates, and how the app shows or dedupes a finding, so it says which sub-rule a list can reach, not what a
    user sees.
    """
    rule = next(r for r in _load("ingredient_interaction_rules.json")["interaction_rules"] if r["id"] == rule_id)
    reached = set().union(*(rule_classes_for(rxcui) for rxcui in rxcuis))
    hits = [
        d["severity"] for d in rule["drug_class_rules"]
        if reached & set(d["profile_gate"]["requires"]["drug_classes_any"])
    ]
    return max(hits, key=SEVERITY_RANK.__getitem__, default=None)


@pytest.mark.parametrize(
    "partner", ["274783", "4821", "73044"], ids=["insulin glargine", "glipizide", "repaglinide"]
)
def test_tirzepatide_with_insulin_or_a_secretagogue_reaches_the_high_risk_sub_rule(partner):
    """D3: tirzepatide alone reaches only the lower-risk sub-rule; with insulin or an insulin secretagogue
    the list also reaches the high-risk one (MOUNJARO 5.3). Medication-class branch only."""
    rule = "RULE_IQM_ALPHA_LIPOIC_ACID_DIABETES"  # monitor for lower risk, caution for high risk and unknown
    assert strongest_severity(rule, ["2601723"]) == "monitor"
    assert strongest_severity(rule, ["2601723", partner]) == "caution"


def test_pramlintide_without_insulin_reaches_the_unknown_tier_sub_rule():
    """D3: pramlintide is indicated with mealtime insulin (SYMLIN 5.2), so alone it reaches the conservative
    unknown-tier sub-rule, not the lower-risk one. Medication-class branch only."""
    assert strongest_severity("RULE_IQM_ALPHA_LIPOIC_ACID_DIABETES", ["139953"]) == "caution"


# Real RxNorm combination sleep and cold products (SCD), resolved to their ingredients
# on RxNav related.json?tty=IN 2026-11-11, the level the app's bridge matches on.
COMBINATIONS = {
    "1092189": ("acetaminophen 500 MG / diphenhydramine hydrochloride 25 MG Oral Tablet", ["161", "3498"]),
    "895664": ("diphenhydramine citrate 38 MG / ibuprofen 200 MG Oral Tablet", ["3498", "5640"]),
    "1052928": ("diphenhydramine hydrochloride 25 MG / phenylephrine hydrochloride 10 MG Oral Tablet", ["3498", "8163"]),
    "1046751": (
        "acetaminophen 325 MG / diphenhydramine hydrochloride 25 MG / phenylephrine hydrochloride 5 MG Oral Tablet",
        ["161", "3498", "8163"],
    ),
}


@pytest.mark.parametrize("scd", COMBINATIONS, ids=lambda scd: COMBINATIONS[scd][0])
def test_combination_sleep_and_cold_products_reach_anticholinergic_rules(scd):
    """The products' ingredients join the anticholinergic rule class. This proves the class join only; the
    app's resolution of a saved product to these ingredients is tested in the app repo."""
    ingredients = COMBINATIONS[scd][1]
    reached = set().union(*(rule_classes_for(rxcui) for rxcui in ingredients))
    assert reached & sub_rule_gate("RULE_IQM_HUPERZINE_A_ANTICHOLINERGICS", "anticholinergics")


def test_thyroid_vocabulary_names_replacement_medicines_only():
    """D1: methimazole inhibits thyroid hormone synthesis; it is not a replacement."""
    entry = next(e for e in _load("drug_class_vocab.json")["drug_classes"] if e["id"] == "thyroid_medications")
    text = " ".join([entry["notes"], *entry["examples"]]).lower()
    for antithyroid in ("methimazole", "propylthiouracil", "modulate"):
        assert antithyroid not in text
    # The 4-hour spacing is the levothyroxine label's, for binders such as calcium
    # carbonate and ferrous sulfate; it was stated for iodine, kelp, soy and biotin.
    assert "separate by 4 hours from levothyroxine" not in entry["notes"]
    assert "calcium carbonate" in entry["notes"] and "stop biotin at least 2 days" in entry["notes"]
    notes = _load("drug_classes.json")["classes"]["class:thyroid_medications"]["notes"]
    assert "open for PharmD review" not in notes


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


def test_anticholinergic_rule_text_fits_medicines_whose_anticholinergic_effect_is_a_side_effect():
    """D2 widened the class to diphenhydramine and tricyclics, so the rules it gates
    must not promise lost efficacy, or a cancelled effect, for every member."""
    rules = {r["id"]: r for r in _load("ingredient_interaction_rules.json")["interaction_rules"]}

    def sub(rule_id):
        return next(d for d in rules[rule_id]["drug_class_rules"] if d["drug_class_id"] == "anticholinergics")

    gpc = sub("RULE_IQM_ALPHA_GPC_ANTICHOLINERGICS")
    assert "Monitor for loss of efficacy" not in gpc["action"]
    assert "taken for its anticholinergic action" in gpc["action"]
    assert "side effect" in gpc["mechanism"] and "not established" in gpc["mechanism"]
    hup = sub("RULE_IQM_HUPERZINE_A_ANTICHOLINERGICS")
    assert "cancel" not in hup["alert_body"] and hup["severity"] == "avoid"
