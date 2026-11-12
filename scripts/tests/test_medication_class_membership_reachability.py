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


CBD = "RULE_BANNED_CBD_INTERACTIONS"
CBD_NAMED = {
    # medicine: (rxcui, its own sub-rule)
    "clobazam": ("21241", "clobazam"), "valproic acid": ("11118", "valproate"), "divalproex": ("266856", "valproate"),
    "stiripentol": ("2054968", "stiripentol"), "everolimus": ("141704", "everolimus"),
    "tacrolimus": ("42316", "tacrolimus"), "sirolimus": ("35302", "sirolimus"), "digoxin": ("3407", "digoxin"),
}


def cbd_sub(drug_class_id: str) -> dict:
    rule = next(r for r in _load("ingredient_interaction_rules.json")["interaction_rules"] if r["id"] == CBD)
    return next(d for d in rule["drug_class_rules"] if d["drug_class_id"] == drug_class_id)


def cbd_findings(rxcuis=(), picker=()) -> set[str]:
    """drug_class_ids of the CBD drug-class sub-rules whose whole gate fires for the profile."""
    import profile_gate_evaluator as pge

    profile = set(picker).union(*(rule_classes_for(r) for r in rxcuis))
    rule = next(r for r in _load("ingredient_interaction_rules.json")["interaction_rules"] if r["id"] == CBD)
    return {
        d["drug_class_id"] for d in rule["drug_class_rules"]
        if pge.evaluate_profile_gate(d["profile_gate"], {"drug_classes": sorted(profile)}, {},
                                     base_severity=d["severity"]).fires
    }


@pytest.mark.parametrize("medicine", CBD_NAMED)
def test_each_medicine_the_cbd_label_names_gets_its_own_finding(medicine):
    """Q5: named medicines, each with its own claim, instead of one claim for every seizure medicine."""
    rxcui, own = CBD_NAMED[medicine]
    findings = cbd_findings([rxcui])
    assert own in findings, medicine
    assert not {"anticonvulsants", "cbd_other_anticonvulsants"} & findings, medicine  # the general review message is for other seizure medicines


@pytest.mark.parametrize("name,rxcui", [("levetiracetam", "114477"), ("lamotrigine", "28439"), ("phenytoin", "8183")])
def test_other_seizure_medicines_get_a_qualified_review_message(name, rxcui):
    """Q5: keep a qualified review message for other seizure medicines until their evidence is assessed."""
    assert cbd_findings([rxcui]) == {"cbd_other_anticonvulsants"}, name
    general = cbd_sub("anticonvulsants")
    assert general["evidence_level"] == "theoretical"
    # Limited to what the label reports; no universal "not assessed" claim, no scope sentence about findings it
    # does not make, and no assumption that a neurologist prescribes the medicine.
    assert "dedicated interaction studies only with clobazam, valproate and stiripentol" in general["mechanism"]
    text = " ".join(general[k] for k in ("mechanism", "action", "alert_body", "informational_note"))
    for stale in ("not been individually", "These findings", "neurologist"):
        assert stale not in text, stale
    assert "doctor who prescribes it" in general["action"] and "doctor who prescribes it" in general["alert_body"]
    assert "May affect seizure medication" not in general["alert_headline"]


@pytest.mark.parametrize("name,rxcui", [
    ("cyclosporine", "3008"), ("adalimumab", "327361"), ("azathioprine", "1256"),
    ("mycophenolate mofetil", "68149"), ("mycophenolic acid", "7145"),
])
def test_cbd_findings_stop_at_the_named_medicines(name, rxcui):
    """Q5: narrow the immunosuppressant rule to the named, supported medicines. Mycophenolate is on the review
    list (DISPOSITIONS batch 4: the label reports higher mycophenolic-acid exposure) and gets no finding yet."""
    assert cbd_findings([rxcui]) == set(), name
    assert "immunosuppressants" not in {d["drug_class_id"] for d in
                                        next(r for r in _load("ingredient_interaction_rules.json")["interaction_rules"]
                                             if r["id"] == CBD)["drug_class_rules"]}


def test_immunosuppressant_picker_alone_gets_no_cbd_finding():
    """The known consequence of Q5's narrowing, held for Dr. Pham (DISPOSITIONS batch 4, H1): the picker class
    holds 90 medicines, mostly biologics, so a conditional card would reach the scope Q5 rejected."""
    assert cbd_findings(picker=["immunosuppressants"]) == set()


@pytest.mark.parametrize("profile", [{"picker": ["cardiac_glycosides"]}, {"rxcuis": ["3403"]}],
                         ids=["digoxin picker", "digitoxin"])
def test_digoxin_picker_reaches_the_conditional_digoxin_finding(profile):
    """The 'Digoxin / Heart rhythm medication' picker keeps a conditional message (Q4: an unknown medicine is not
    assumed absent). The class cannot tell the picker from another cardiac glycoside, so the copy names digoxin."""
    assert cbd_findings(**profile) == {"digoxin"}
    digoxin = cbd_sub("digoxin")
    for key in ("alert_headline", "alert_body", "informational_note", "action"):
        assert "digoxin taken by mouth" in digoxin[key] or "digoxin by mouth" in digoxin[key], key


SEIZURE_FINDINGS = {"clobazam", "valproate", "stiripentol", "anticonvulsants"}


def test_cbd_seizure_findings_do_not_reach_other_benzodiazepines():
    """Alprazolam gets no seizure-medicine finding. Whether it should get the CBD sedation finding (label 7.4,
    other CNS depressants) is a gap that predates Q5, logged in DISPOSITIONS batch 4."""
    assert not cbd_findings(["596"]) & SEIZURE_FINDINGS


def test_cbd_findings_say_what_each_source_measured():
    """Q5's per-medicine claims, and no consumer instruction to change a prescription dose."""
    valproate = cbd_sub("valproate")
    text = " ".join(valproate[k] for k in ("alert_headline", "alert_body", "informational_note", "action")).lower()
    assert "liver" in text and "raise valproate" not in text and "valproate levels" not in text
    assert "did not raise valproate exposure" in valproate["mechanism"]
    assert "active metabolite" in cbd_sub("clobazam")["mechanism"] and "sleepiness" in cbd_sub("clobazam")["alert_body"]
    assert "about 2.5-fold" in cbd_sub("everolimus")["mechanism"]
    tacrolimus = cbd_sub("tacrolimus")
    assert tacrolimus["sources"][0] == "https://pubmed.ncbi.nlm.nih.gov/39601108/"
    assert "4.2-fold" in tacrolimus["mechanism"] and "3.1-fold" in tacrolimus["mechanism"]
    assert "open-label" in tacrolimus["mechanism"] and "interim analysis" in tacrolimus["mechanism"]
    # Both are measured human PK effects, graded alike.
    assert tacrolimus["evidence_level"] == cbd_sub("everolimus")["evidence_level"] == "established"
    for medicine in ("sirolimus", "digoxin"):
        sub = cbd_sub(medicine)
        assert "not measured directly" in sub["alert_body"] and sub["evidence_level"] == "theoretical", medicine
        assert "not one measured with " + medicine in sub["mechanism"], medicine
    for medicine in ("tacrolimus", "sirolimus", "digoxin"):
        sub = cbd_sub(medicine)
        assert "by mouth" in sub["alert_body"] and "by mouth" in sub["action"], medicine
        assert sub["alert_headline"].endswith(medicine + " taken by mouth"), medicine
    # Q5: the measured size belongs to prescription cannabidiol; no visible body states it for CBD in general.
    for drug_class_id in ("clobazam", "valproate", "stiripentol", "everolimus", "tacrolimus", "sirolimus", "digoxin"):
        assert "prescription" in cbd_sub(drug_class_id)["alert_body"].lower(), drug_class_id
    assert "In a controlled study, CBD raised" not in tacrolimus["alert_body"]
    for drug_class_id in ("clobazam", "valproate", "stiripentol", "everolimus", "tacrolimus", "sirolimus", "digoxin",
                          "anticonvulsants"):
        action = cbd_sub(drug_class_id)["action"].lower()
        for instruction in ("dose reduction", "reduce the dose", "monitor ", "adjust"):
            assert instruction not in action, (drug_class_id, instruction)
        assert "yourself" in action, drug_class_id


def test_seizure_condition_guidance_makes_an_accurate_claim():
    rule = next(r for r in _load("ingredient_interaction_rules.json")["interaction_rules"] if r["id"] == CBD)
    seizure = next(c for c in rule["condition_rules"] if c["condition_id"] == "seizure_disorder")
    assert "Use only pharmaceutical-grade CBD" not in seizure["action"]
    assert "in place of prescribed seizure treatment" in seizure["action"]
    assert "seizure threshold" not in seizure["informational_note"]
    assert "Lennox-Gastaut syndrome, Dravet syndrome and tuberous sclerosis complex" in seizure["mechanism"]
    assert "made liver-enzyme rises more common (valproate)" in seizure["mechanism"]
    assert "or liver-enzyme rises (valproate)" not in seizure["mechanism"]


def test_cbd_findings_say_the_wording_is_agent_work():
    rule = next(r for r in _load("ingredient_interaction_rules.json")["interaction_rules"] if r["id"] == CBD)
    owner = rule["review_owner"]
    assert owner.startswith("Dr. Pham (signed answers 2026-11-12, Q5") and "by agent" in owner
    # The signature covers the Q5 sub-rules only; the other sub-rules were not re-reviewed.
    assert "anticoagulant, sedative and pregnancy sub-rules are unchanged" in owner
    for drug_class_id in ("clobazam", "valproate", "stiripentol", "everolimus", "tacrolimus", "sirolimus", "digoxin",
                          "anticonvulsants"):
        notes = cbd_sub(drug_class_id)["clinical_review"]["notes"]
        assert "severity and evidence grading: agent work, not reviewed by Dr. Pham" in notes, drug_class_id
    assert rule["last_reviewed"] == "2026-11-12"


@pytest.mark.parametrize("class_id,parent", [
    ("clobazam", "anticonvulsants"), ("valproate", "anticonvulsants"), ("stiripentol", "anticonvulsants"),
    ("everolimus", "immunosuppressants"), ("tacrolimus", "immunosuppressants"), ("sirolimus", "immunosuppressants"),
    ("digoxin", "cardiac_glycosides"),
])
def test_cbd_rule_class_vocabulary_reuses_approved_copy(class_id, parent):
    """The vocabulary's sign-off covers only approved strings, so the new rule-only entries reuse their parent's.
    Dr. Pham's Q5 sentences for clobazam and valproate wait for her confirmation of the contract adaptation."""
    vocab_blob = _load("drug_class_vocab.json")
    vocab = {e["id"]: e for e in vocab_blob["drug_classes"]}
    for field in ("group_label", "commonly_used_for"):
        assert vocab[class_id][field] == vocab[parent][field], (class_id, field)
    assert vocab[class_id]["user_selectable"] is False
    review = vocab_blob["_metadata"]["consumer_copy_review"]
    assert review["status"] == "approved" and "wait for her confirmation" in review["note"]


@pytest.mark.parametrize("class_id,atc", [("stiripentol", "N03AX"), ("everolimus", "L04AH"), ("tacrolimus", "L04AD"),
                                          ("sirolimus", "L04AH"), ("digoxin", "C01AA")])
def test_single_medicine_classes_name_the_systemic_atc_class(class_id, atc):
    """The eye-preparation class (S01XA) is not sirolimus's systemic class."""
    assert _load("drug_classes.json")["classes"][f"class:{class_id}"]["rxclass_id"] == atc


def test_single_medicine_citation_topics_need_the_medicine_name():
    """A source about another member of the same family must not pass as on-topic for a single-medicine class."""
    from api_audit.verify_interaction_rules_citations import TOPIC_STEMS

    names = {"clobazam": "clobazam", "valproate": "valproate divalproex", "stiripentol": "stiripentol",
             "everolimus": "everolimus", "tacrolimus": "tacrolimus", "sirolimus": "sirolimus rapamycin",
             "digoxin": "digoxin"}
    for class_id, name in names.items():
        assert TOPIC_STEMS[class_id] and all(stem in name for stem in TOPIC_STEMS[class_id]), class_id


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


def test_cbd_general_review_survives_stiripentol_in_mixed_regimen():
    assert cbd_findings(["2054968", "114477"]) == {
        "stiripentol", "cbd_other_anticonvulsants",
    }


def test_emsam_supplement_rule_requires_patch_identity():
    import profile_gate_evaluator as pge
    rules = _load("ingredient_interaction_rules.json")["interaction_rules"]
    same = next(rule for rule in rules if rule["id"] == "RULE_IQM_SAME")
    for rx, severity in [("865208", "contraindicated"), ("9639", "avoid"), ("", None)]:
        classes = sorted(rule_classes_for(rx)) if rx else []
        findings = [
            row["severity"] for row in same["drug_class_rules"]
            if pge.evaluate_profile_gate(row["profile_gate"], {"drug_classes": classes}, {},
                                         base_severity=row["severity"]).fires
        ]
        assert findings == ([severity] if severity else [])


def test_emsam_patch_profile_members_and_exact_pairs_agree():
    patch = _load("drug_classes.json")["classes"]["class:emsam_patch"]
    ids = set(patch["member_rxcuis"])
    assert {"9639", "1158174"}.isdisjoint(ids)
    pairs = {
        row["agent1_id"]: row
        for row in _load("curated_interactions/curated_interactions_v1.json")["interactions"]
        if row["id"].startswith("DSI_EMSAM_SAME_")
    }
    assert set(pairs) == ids
    assert all(row["severity"] == "Contraindicated" for row in pairs.values())


def test_cbd_subset_preserves_existing_pair_export_class_tags():
    from build_interaction_db import build_rxcui_to_class

    authored = _load("drug_classes.json")
    classes = authored["classes"]
    scoped = classes["class:cbd_other_anticonvulsants"]["member_rxcuis"]
    previous = {"classes": {key: value for key, value in classes.items()
                            if key != "class:cbd_other_anticonvulsants"}}
    before, after = map(build_rxcui_to_class, (previous, authored))
    assert all(after[rx] == before[rx] for rx in scoped)
