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
        "antimuscarinics",
        # Dr. Pham Q6 (2026-11-12): the members taken for their antimuscarinic effect.
        # Tricyclics and diphenhydramine stay in anticholinergics only (Q4 keeps their identity).
        {
            "oxybutynin": "32675", "tolterodine": "119565", "trospium": "236778", "solifenacin": "322167",
            "scopolamine": "9601", "benztropine": "1424", "trihexyphenidyl": "10811", "hyoscyamine": "153970",
            "glycopyrronium": "1546438", "dicyclomine": "3361",
        },
        {
            "amitriptyline": "704", "nortriptyline": "7531", "doxepin": "3638", "imipramine": "5691",
            "diphenhydramine": "3498", "mirabegron": "1300786", "donepezil": "135447",
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


HUPERZINE = "RULE_IQM_HUPERZINE_A_ANTICHOLINERGICS"
ALPHA_GPC = "RULE_IQM_ALPHA_GPC_ANTICHOLINERGICS"
ANTIMUSCARINIC_USERS = {"oxybutynin": "32675", "tolterodine": "119565", "benztropine": "1424", "scopolamine": "9601"}
INCIDENTAL_USERS = {"amitriptyline": "704", "doxepin": "3638", "nortriptyline": "7531", "diphenhydramine": "3498"}


def firing(rule_id: str, rxcuis=(), picker=()) -> list[tuple[str, str]]:
    """(drug_class_id, severity) of each drug-class sub-rule whose whole gate fires for a profile: the classes of
    the entered medicines plus any picker class, as the app builds it. Excludes apply to the whole profile."""
    import profile_gate_evaluator as pge

    profile = set(picker).union(*(rule_classes_for(r) for r in rxcuis))
    rule = next(r for r in _load("ingredient_interaction_rules.json")["interaction_rules"] if r["id"] == rule_id)
    return [
        (d["drug_class_id"], d["severity"]) for d in rule["drug_class_rules"]
        if pge.evaluate_profile_gate(d["profile_gate"], {"drug_classes": sorted(profile)}, {},
                                     base_severity=d["severity"]).fires
    ]


def anticholinergic_sub(rule_id: str, drug_class_id: str) -> dict:
    rule = next(r for r in _load("ingredient_interaction_rules.json")["interaction_rules"] if r["id"] == rule_id)
    return next(d for d in rule["drug_class_rules"] if d["drug_class_id"] == drug_class_id)


@pytest.mark.parametrize("rxcui", ANTIMUSCARINIC_USERS.values(), ids=ANTIMUSCARINIC_USERS)
def test_a_medicine_taken_for_its_antimuscarinic_effect_gets_huperzine_avoid_and_alpha_gpc_caution(rxcui):
    """Q6: huperzine A, avoid unsupervised combination; alpha-GPC, caution with limited evidence."""
    assert firing(HUPERZINE, [rxcui]) == [("antimuscarinics", "avoid")]
    assert firing(ALPHA_GPC, [rxcui]) == [("antimuscarinics", "caution")]


@pytest.mark.parametrize("rxcui", INCIDENTAL_USERS.values(), ids=INCIDENTAL_USERS)
def test_a_medicine_with_incidental_anticholinergic_effects_gets_caution_and_a_note(rxcui):
    """Q6: huperzine A + a tricyclic or diphenhydramine is caution with an evidence limitation; alpha-GPC asserts
    no loss of benefit from class membership alone. Q4: doxepin keeps its identity (no low-dose or topical carve-out)."""
    assert firing(HUPERZINE, [rxcui]) == [("anticholinergics", "caution")]
    assert firing(ALPHA_GPC, [rxcui]) == [("anticholinergics", "informational")]


def test_both_kinds_together_show_only_the_stronger_finding():
    """Excludes are whole-profile: oxybutynin with amitriptyline reads as the antimuscarinic finding once."""
    assert firing(HUPERZINE, ["32675", "704"]) == [("antimuscarinics", "avoid")]
    assert firing(ALPHA_GPC, ["32675", "704"]) == [("antimuscarinics", "caution")]


def test_a_picker_only_profile_keeps_the_uncertainty_and_the_avoid_instruction():
    """Q4: when the medicine is unknown, keep the uncertainty and ask. The picker-only profile gets the broad
    sub-rule, and the app shows its headline and body, so those carry both branches: someone on a medicine like
    oxybutynin is told not to combine without approval, and nothing assumes a tricyclic or diphenhydramine."""
    assert firing(HUPERZINE, picker=["anticholinergics"]) == [("anticholinergics", "caution")]
    assert firing(ALPHA_GPC, picker=["anticholinergics"]) == [("anticholinergics", "informational")]
    hup = anticholinergic_sub(HUPERZINE, "anticholinergics")
    gpc = anticholinergic_sub(ALPHA_GPC, "anticholinergics")
    for sub in (hup, gpc):
        assert "tricyclic" not in sub["alert_headline"].lower() and "diphenhydramine" not in sub["alert_headline"]
        assert "anticholinergic medicine" in sub["alert_headline"]
        assert "oxybutynin" in sub["alert_body"] and "anticholinergic" in sub["alert_body"]
    assert "do not combine unless your prescriber approves; otherwise ask first" in hup["alert_body"]
    assert "such as oxybutynin, do not combine them unless your prescriber approves" in hup["action"]
    assert "by mouth or on the skin" in hup["action"]
    assert "tell your prescriber about alpha-GPC" in gpc["alert_body"]


def test_anticholinergic_copy_claims_no_cancelled_effect_or_treatment_failure():
    """Q6: eliminate "cancel each other out" and qualify the consequence."""
    rules = _load("ingredient_interaction_rules.json")["interaction_rules"]
    pairs = (DATA / "curated_interactions/curated_interactions_v1.json").read_text()
    assert "cancel each other" not in json.dumps(rules).lower() and "cancel each other" not in pairs.lower()
    for rule_id in (HUPERZINE, ALPHA_GPC):
        for drug_class_id in ("antimuscarinics", "anticholinergics"):
            sub = anticholinergic_sub(rule_id, drug_class_id)
            text = " ".join(sub[k] for k in ("alert_headline", "alert_body", "informational_note", "action",
                                             "mechanism")).lower()
            assert "cancel" not in text and "loss of efficacy" not in text, (rule_id, drug_class_id)
    note = anticholinergic_sub(ALPHA_GPC, "anticholinergics")
    assert (note["severity"], note["direction"], note["evidence_level"]) == ("informational", "neutral", "theoretical")
    consumer = " ".join(note[k] for k in ("alert_headline", "alert_body", "informational_note")).lower()
    for claim in ("less well", "lessen", "reduce", "work against", "blunt"):
        assert claim not in consumer, claim
    subset = anticholinergic_sub(ALPHA_GPC, "antimuscarinics")
    assert subset["evidence_level"] == "limited"
    assert "does not show that alpha-GPC makes these medicines ineffective" in subset["mechanism"]


def test_doxepin_wording_is_qualified_without_a_strength_cutoff_or_a_topical_exemption():
    """Q4: SILENOR's above-6-mg statement is not an interaction cutoff; ZONALON reports systemic absorption."""
    hup = anticholinergic_sub(HUPERZINE, "anticholinergics")
    assert (hup["severity"], hup["evidence_level"]) == ("caution", "theoretical")
    assert "so 6 mg is not an interaction cutoff" in hup["mechanism"]
    # SILENOR lists anticholinergic effects among those seen above 6 mg yet contraindicates 3-6 mg use in untreated
    # narrow-angle glaucoma or severe urinary retention (4.3): "only above 6 mg" overstated the label.
    assert "contraindicates it in untreated narrow-angle glaucoma or severe urinary retention" in hup["mechanism"]
    notes = _load("drug_classes.json")["classes"]["class:anticholinergics"]["notes"]
    assert "only above 6 mg" not in notes and "only above 6 mg" not in hup["mechanism"]
    assert "systemic anticholinergic effects after skin application" in hup["mechanism"]
    assert any("1bec1223" in s for s in hup["sources"]) and any("5f302247" in s for s in hup["sources"])
    assert hup["profile_gate"]["dose"] is None and not hup["profile_gate"]["excludes"]["product_forms_any"]
    for rule_id in (HUPERZINE, ALPHA_GPC):
        assert anticholinergic_sub(rule_id, "anticholinergics")["profile_gate"]["excludes"]["drug_classes_any"] == [
            "antimuscarinics"]


def test_the_antimuscarinic_subset_sits_inside_the_anticholinergic_identity_class():
    """Q6: create the narrower rule subset without corrupting the broader identity class."""
    classes = _load("drug_classes.json")["classes"]
    subset = set(classes["class:antimuscarinics"]["member_rxcuis"])
    broad = set(classes["class:anticholinergics"]["member_rxcuis"])
    assert subset < broad
    assert broad - subset == {"704", "722", "2597", "3247", "3498", "3638", "5691", "7531", "8886", "10834"}
    # Exact ATC codes for single members, as the parent records them: a group code such as A04AD (other
    # antiemetics) would name unrelated medicines.
    assert classes["class:antimuscarinics"]["atc_codes"] == [
        "A03AA07", "A03AB02", "A03BA03", "A04AD01", "G04BD", "N04AA", "N04AC01"]
    assert set(classes["class:antimuscarinics"]["atc_codes"]) <= set(classes["class:anticholinergics"]["atc_codes"])


def test_anticholinergic_findings_say_the_wording_is_agent_work():
    """Dr. Pham signed the Q4/Q6 severities and scope; the strings are agent wording and must say so."""
    for rule_id in (HUPERZINE, ALPHA_GPC):
        rule = next(r for r in _load("ingredient_interaction_rules.json")["interaction_rules"] if r["id"] == rule_id)
        assert rule["review_owner"].startswith("Dr. Pham (signed answers 2026-11-12, Q4 and Q6")
        assert "by agent" in rule["review_owner"]
        for sub in rule["drug_class_rules"]:
            assert "agent work, not reviewed by Dr. Pham" in sub["clinical_review"]["notes"], (rule_id, sub["drug_class_id"])
