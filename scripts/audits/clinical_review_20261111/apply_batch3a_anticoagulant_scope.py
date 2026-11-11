"""Batch 3a of Dr. Pham's 2026-11-11 review: anticoagulant scope (rows A2, A4-A10 and their E sources).

Run once from the repo root:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch3a_anticoagulant_scope.py

Decisions: DR_PHAM_REVIEW_20261111.md (A2, A4-A10 and her cranberry response); rows mapped in
DISPOSITIONS_20261111.md. Every passage below was read by the agent on 2026-11-11: the DailyMed warfarin
label (setid ab98f729-31b4-2b6d-e053-2995a90afed7, section 7) and LOVAZA label (section 7.1) from the v2 SPL
service, the UK warfarin 5 mg SmPC (emc 14333, section 4.5, last updated 4 Jul 2025), and PubMed abstracts
17723077, 15801937, 18516070, 19553405 and 18363538.

Warfarin-specific evidence was gated on `anticoagulants` minus `doacs`: warfarin users and people whose blood
thinner is unknown keep the finding; a DOAC user no longer gets a warfarin card. apply_batch3a_vka_scope.py
replaced that gate, because a DOAC anywhere in the medicine list also vetoed an identified warfarin.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

CURATED = REPO / "scripts/data/curated_interactions/curated_interactions_v1.json"
RULES = REPO / "scripts/data/ingredient_interaction_rules.json"
HIGH_DOSE_EXEMPTIONS = REPO / "scripts/data/high_dose_rule_exemptions.json"
GOLD_CASES = REPO / "scripts/data/profile_gate_test_cases.json"

REVIEW_FILE = "audits/clinical_review_20261111/DR_PHAM_REVIEW_20261111.md"
REVIEW_NOTE = f"Severity and scope decided by Dr. Pham (clinical review 2026-11-11, {REVIEW_FILE}); sources read by agent."
CLINICAL_REVIEW = {"reviewer": "Dr. Pham", "reviewed_at": "2026-11-11", "file": REVIEW_FILE}

WARFARIN_LABEL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=ab98f729-31b4-2b6d-e053-2995a90afed7"
UK_WARFARIN = "https://www.medicines.org.uk/emc/product/14333/smpc"
LOVAZA = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=21cfa4ce-0b05-47ed-b268-339eb1b83b75"
NCCIH = "https://www.nccih.nih.gov/health/"
ODS_OMEGA3 = "https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/"


def pubmed(pmid: str) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def verification(note: str) -> dict:
    return {
        "status": "verified",
        "verified_at": "2026-11-11",
        "verified_with": {"rxnorm": True, "umls": True, "pubmed": True},
        "method": "agent_label_content_review_2026_11_11",
        "notes": f"{note} {REVIEW_NOTE}",
    }


def warfarin_only(sub: dict) -> None:
    """Keep warfarin and unknown blood thinners; skip people whose blood thinner is a DOAC."""
    excluded = sub["profile_gate"]["excludes"]["drug_classes_any"]
    assert excluded == [], sub["drug_class_id"]
    excluded.append("doacs")


def no_floor(sub: dict) -> None:
    sub["min_effective_dose"] = None
    sub["materiality"] = "presence"


# ---------------------------------------------------------------- pairs (curated_interactions_v1.json)

def sjw_pair(row: dict) -> None:
    assert row["severity"] == "Major"
    row.update({
        "management": (
            "Avoid St. John's wort while you take warfarin. If you already take both, do not stop either one on "
            "your own: tell your anticoagulation team first, because starting or stopping St. John's wort can "
            "change how well warfarin works and your INR."
        ),
        "source_urls": [UK_WARFARIN, WARFARIN_LABEL, *row["source_urls"]],
        "evidence_notes": (
            "The UK warfarin SmPC (section 4.5) says St John's wort preparations must not be used with warfarin "
            "because of a proven risk of reduced warfarin levels and effect. The US warfarin label lists St. John's "
            "wort among botanicals that may decrease warfarin's effect and asks for more frequent INR checks when a "
            "botanical is started or stopped. Other vitamin-K antagonists were not verified separately."
        ),
        "verification": verification("UK SmPC 14333 and the DailyMed warfarin label read."),
    })


def coq10_pair(row: dict) -> None:
    assert row["severity"] == "Moderate"
    row.update({
        "severity": "Minor",
        # Minor pairs sit in the background lane (verify_interactions check 12); the lane is not exported.
        "display_layer": "background",
        "background_rationale": (
            "Warfarin-label example of a botanical that may reduce warfarin's effect, with mixed clinical data; "
            "an INR monitoring signal rather than an avoid instruction (Dr. Pham, 2026-11-11)."
        ),
        "mechanism": (
            "The warfarin label lists coenzyme Q10 among botanicals that may decrease warfarin's effect. Clinical "
            "evidence is mixed, and a negative trial does not remove the label's concern."
        ),
        "management": (
            "Tell your anticoagulation team before you start, stop or substantially change CoQ10, so they can "
            "decide whether your INR needs extra checks."
        ),
        "source_urls": [WARFARIN_LABEL, f"{NCCIH}coenzyme-q10"],
        "evidence_basis": "label_regulatory",
        "clinical_confidence": "low",
        "evidence_notes": (
            "Warfarin label section 7: some botanicals may decrease warfarin's effect (co-enzyme Q10, St. John's "
            "wort, ginseng); perform more frequent INR monitoring when starting or stopping botanicals. Scope is "
            "warfarin only; the label does not cover other anticoagulants."
        ),
        "verification": verification("DailyMed warfarin label section 7 read."),
    })


def ginkgo_pair(row: dict) -> None:
    assert row["severity"] == "Major"
    row.update({
        "severity": "Moderate",
        "management": (
            "Talk to your anticoagulation team before adding ginkgo. If you take both, ask how bleeding should be "
            "monitored, report unusual bruising or bleeding promptly, and do not change your warfarin dose yourself."
        ),
        "source_urls": [WARFARIN_LABEL, *row["source_urls"]],
        "evidence_notes": (
            "The warfarin label names Ginkgo biloba among botanicals that may cause bleeding and whose effects would "
            "be expected to add to warfarin's. Observational data suggest more bleeding; controlled studies at usual "
            "doses found no significant effect. No dose has been shown to remove the concern."
        ),
        "verification": verification("DailyMed warfarin label section 7 read; NCCIH ginkgo and PMID 26958257 kept."),
    })


def garlic_pair(row: dict) -> None:
    assert row["severity"] == "Moderate"
    row.update({
        "mechanism": (
            "Garlic supplements may affect platelet function. The warfarin label names garlic among botanicals that "
            "may cause bleeding and whose effects would be expected to add to warfarin's."
        ),
        "source_urls": [WARFARIN_LABEL, f"{NCCIH}garlic", pubmed("18516070")],
        "source_pmids": ["18516070"],
        "evidence_notes": (
            "This applies to garlic supplements and concentrates, not ordinary food use. Evidence is mainly case "
            "reports; a small crossover study in 12 healthy men found no change in warfarin's effect with garlic "
            "(PMID 18516070), which does not rule out an effect in long-term users."
        ),
        "verification": verification("DailyMed warfarin label section 7, NCCIH garlic and PMID 18516070 read."),
    })


def glucosamine_pair(row: dict) -> None:
    assert row["severity"] == "Minor"
    for key in ("display_layer", "background_rationale"):
        row.pop(key)
    row.update({
        "severity": "Moderate",
        "mechanism": (
            "An FDA pharmacovigilance review found 20 reports of altered coagulation, such as a higher INR or "
            "bleeding, when glucosamine or glucosamine-chondroitin was used with warfarin; one report described a "
            "bleed in the brain. The mechanism is unknown."
        ),
        "management": (
            "Tell your anticoagulation team before you start, stop or change glucosamine, including "
            "glucosamine-chondroitin products, so they can decide how to check your INR. Report unusual bruising or "
            "bleeding."
        ),
        "source_urls": [pubmed("18363538"), UK_WARFARIN, f"{NCCIH}glucosamine-and-chondroitin-for-osteoarthritis"],
        "source_pmids": ["18363538"],
        "evidence_basis": "observational",
        "clinical_confidence": "medium",
        "evidence_notes": (
            "Knudsen and Sokol 2008 (PMID 18363538): 20 MedWatch reports of altered coagulation with warfarin, one "
            "with an intraventricular bleed and subdural hematoma. The UK warfarin SmPC (section 4.5) says the "
            "combination is not recommended. Scope is warfarin only."
        ),
        "verification": verification("PMID 18363538 and UK SmPC 14333 read."),
    })


def cranberry_pair(row: dict) -> None:
    assert row["severity"] == "Moderate"
    row.update({
        "mechanism": (
            "Evidence is mixed. In 12 healthy men, cranberry concentrate capsules raised the INR response to a "
            "single warfarin dose by about 30% without changing warfarin levels (PMID 18516070). In 30 people on "
            "stable warfarin, a daily glass of cranberry juice for 2 weeks did not cause a clinically important "
            "change (PMID 19553405). Case reports describe a higher INR or bleeding. The studies used different "
            "preparations, so neither result applies to every product."
        ),
        "management": (
            "Contact your anticoagulation team before you start, stop or materially change cranberry supplements or "
            "concentrates."
        ),
        "source_urls": [UK_WARFARIN, f"{NCCIH}cranberry", pubmed("18516070"), pubmed("19553405")],
        "source_pmids": ["18516070", "19553405"],
        "evidence_basis": "clinical_literature",
        "evidence_notes": (
            "Applies to cranberry supplements, concentrates and unknown preparations; no dose has been shown to "
            "remove the concern. Jurisdiction: the UK warfarin SmPC (section 4.5) says patients should be advised to "
            "avoid cranberry products and that INR supervision should be considered with regular cranberry juice; "
            "US NCCIH describes the evidence as conflicting and advises talking with a provider. Not a formal "
            "contraindication."
        ),
        "verification": verification("UK SmPC 14333, NCCIH cranberry and PMIDs 18516070, 19553405 read."),
    })


def ginger_pair(row: dict) -> None:
    assert row["severity"] == "Minor"
    for key in ("display_layer", "background_rationale"):
        row.pop(key)
    row.update({
        "agent2_name": "Ginger (supplement)",
        "severity": "Moderate",
        "mechanism": (
            "In a cohort of 171 people taking warfarin, ginger use was associated with self-reported bleeding (odds "
            "ratio 3.2; PMID 17723077). In a crossover study in 12 healthy men, ginger did not change INR or "
            "platelet aggregation after a single warfarin dose (PMID 15801937). Neither study sets a safe dose or "
            "shows that ginger in food carries the same risk."
        ),
        "management": (
            "Talk to your anticoagulation team before using ginger supplements or concentrates, and report unusual "
            "bruising or bleeding."
        ),
        "source_urls": [pubmed("17723077"), pubmed("15801937")],
        "source_pmids": ["17723077", "15801937"],
        "evidence_basis": "observational",
        "evidence_notes": (
            "Limited and conflicting evidence: an observational association with self-reported bleeding versus a "
            "small single-dose study with no INR or platelet effect. Applies to supplemental or concentrated ginger."
        ),
        "verification": verification("PMIDs 17723077 and 15801937 read; NCCIH ginger removed (no bleeding content)."),
    })


def fish_oil_pair(row: dict) -> None:
    assert row["severity"] == "Moderate"
    row.update({
        "severity": "Minor",
        "display_layer": "background",
        "background_rationale": (
            "Possible additive bleeding tendency extrapolated from the prescription omega-3 label's advice to monitor "
            "people on drugs that affect coagulation; no NSAID-specific source (Dr. Pham, 2026-11-11)."
        ),
        "mechanism": (
            "Omega-3 fatty acids may prolong bleeding time. The prescription omega-3 label (LOVAZA) says people "
            "taking it with a drug that affects coagulation should be monitored periodically; the trials in that "
            "label did not show clinically significant bleeding. Applying this to over-the-counter fish oil and to "
            "NSAIDs is an extrapolation, since the label names neither. Prescription purified EPA (icosapent ethyl) "
            "has its own label and is not covered here."
        ),
        "management": (
            "If you take an NSAID regularly, mention fish oil to your clinician or pharmacist, especially if you "
            "have other bleeding risks, and watch for unusual bruising or bleeding."
        ),
        "source_urls": [LOVAZA, ODS_OMEGA3],
        "evidence_notes": (
            "LOVAZA section 7.1 (anticoagulants or other drugs affecting coagulation): monitor periodically. "
            "Extrapolated to supplement fish oil and NSAIDs; no fish-oil amount is set as a cutoff."
        ),
        "verification": verification("LOVAZA label section 7.1 read."),
    })


PAIRS = {
    "DSI_WAR_SJW": sjw_pair,
    "DSI_WAR_COQ10": coq10_pair,
    "DSI_WAR_GINKGO": ginkgo_pair,
    "DSI_WAR_GARLIC": garlic_pair,
    "DSI_WAR_GLUCOSAMINE": glucosamine_pair,
    "DSI_WAR_CRANBERRY": cranberry_pair,
    "DSI_WAR_GINGER": ginger_pair,
    "DSI_NSAID_FISHOIL": fish_oil_pair,
}


# ---------------------------------------------------------------- profile rules (ingredient_interaction_rules.json)

def sjw_rule(sub: dict) -> None:
    assert sub["severity"] == "contraindicated"
    warfarin_only(sub)
    sub.update({
        "severity": "avoid",
        "action": (
            "If you take warfarin, avoid St. John's wort. If you already take both, tell your anticoagulation team "
            "before stopping either, because starting or stopping it can change your INR."
        ),
        "alert_headline": "Avoid St. John's wort with warfarin",
        "alert_body": (
            "If you take warfarin, avoid St. John's wort: it can reduce warfarin's effect. Tell your prescriber "
            "about any use or change so INR checks can be planned."
        ),
        "sources": [UK_WARFARIN, WARFARIN_LABEL, *sub["sources"]],
    })


def coq10_rule(sub: dict) -> None:
    assert sub["severity"] == "monitor"
    warfarin_only(sub)
    sub.update({
        "evidence_level": "probable",
        "mechanism": (
            "The warfarin label lists coenzyme Q10 among botanicals that may decrease warfarin's effect and asks for "
            "more frequent INR checks when a botanical is started or stopped. Clinical evidence is mixed."
        ),
        "action": (
            "Tell your anticoagulation team before you start, stop or substantially change CoQ10 while taking "
            "warfarin, so they can decide whether your INR needs extra checks."
        ),
        "informational_note": "CoQ10 may reduce warfarin's effect — relevant to anyone on warfarin.",
        "sources": [WARFARIN_LABEL, f"{NCCIH}coenzyme-q10"],
    })


def ginkgo_rule(sub: dict) -> None:
    assert sub["severity"] == "caution"
    no_floor(sub)
    sub.update({
        "evidence_level": "moderate",
        "mechanism": (
            "Ginkgo may increase the risk of bleeding in people taking anticoagulants such as warfarin. The warfarin "
            "label names Ginkgo biloba among botanicals whose effects would be expected to add to warfarin's."
        ),
        "action": (
            "If you take a blood thinner, talk to your prescriber before using ginkgo and ask how bleeding should be "
            "monitored."
        ),
        "alert_body": (
            "Ginkgo may increase bleeding with blood thinners such as warfarin. Talk to your prescriber before "
            "using it, and report unusual bruising or bleeding."
        ),
        "sources": [WARFARIN_LABEL, f"{NCCIH}ginkgo"],
    })


def ginkgo_antiplatelet_rule(sub: dict) -> None:
    assert sub["severity"] == "caution"
    no_floor(sub)


def garlic_rule(sub: dict) -> None:
    assert sub["severity"] == "monitor"
    no_floor(sub)
    sub.update({
        "severity": "caution",
        "evidence_level": "probable",
        "mechanism": (
            "Garlic supplements can affect platelet function. The warfarin label names garlic among botanicals whose "
            "bleeding effects would be expected to add to warfarin's; the risk rises further with antiplatelets."
        ),
        "action": (
            "If you take a blood thinner, talk to your prescriber before starting, stopping or changing a garlic "
            "supplement, and report unusual bruising or bleeding."
        ),
        "alert_headline": "May add to blood-thinner effects",
        "alert_body": (
            "Garlic supplements may increase bleeding risk with blood thinners such as warfarin. Talk to your "
            "prescriber before using them."
        ),
        "informational_note": "Garlic supplements can affect platelet function — relevant to anyone on blood thinners.",
        "sources": [WARFARIN_LABEL, f"{NCCIH}garlic"],
    })


def garlic_antiplatelet_rule(sub: dict) -> None:
    assert sub["severity"] == "caution"
    no_floor(sub)
    assert "600" not in sub["mechanism"] + sub["action"] + sub["alert_body"]


def drop_garlic_anticoagulant_tier(rule: dict) -> None:
    """The rule-level tier (> 1200 mg avoid, otherwise monitor) replaced the sub-rule severity in the enricher, so
    Dr. Pham's caution never shipped. Its cited source (NCCIH garlic) states no dose; the packet did not show it."""
    tiers = [t for t in rule["dose_thresholds"]
             if t.get("scope") == "drug_class" and t.get("target_id") == "anticoagulants"]
    assert len(tiers) == 1 and tiers[0]["value"] == 1200, tiers
    rule["dose_thresholds"].remove(tiers[0])


def glucosamine_rule(sub: dict) -> None:
    assert sub["severity"] == "caution"
    warfarin_only(sub)
    sub.update({
        "evidence_level": "moderate",
        "mechanism": (
            "An FDA pharmacovigilance review (Knudsen and Sokol 2008) found 20 reports of altered coagulation, such "
            "as a higher INR or bleeding, with glucosamine or glucosamine-chondroitin and warfarin, including one "
            "intraventricular bleed and subdural hematoma. The UK warfarin label says the combination is not "
            "recommended. The mechanism is unknown."
        ),
        "action": (
            "Tell your anticoagulation team before you start, stop or change glucosamine while taking warfarin, so "
            "they can decide how to check your INR."
        ),
        # 23946031 (Can Fam Physician 2013, PMC3743701): teaching case, INR 3.9 after a glucosamine-chondroitin
        # supplement was started; full text read 2026-11-11.
        "sources": [pubmed("18363538"), pubmed("14986566"), pubmed("23946031"), UK_WARFARIN],
    })


def cranberry_rule(sub: dict) -> None:
    assert sub["severity"] == "monitor"
    warfarin_only(sub)
    sub.update({
        "severity": "caution",
        "evidence_level": "probable",
        "mechanism": (
            "Human evidence is mixed: cranberry concentrate capsules raised the INR response to warfarin in healthy "
            "men, while cranberry juice did not cause a clinically important change in people on stable warfarin. "
            "Preparations differ, and no dose has been shown to remove the concern."
        ),
        "action": (
            "If you take warfarin, contact your anticoagulation team before starting, stopping or materially "
            "changing cranberry supplements or concentrates."
        ),
        "alert_body": (
            "Cranberry supplements and concentrates may raise INR in people taking warfarin; the evidence is mixed. "
            "Talk to your anticoagulation team before starting or changing them."
        ),
        "informational_note": (
            "Cranberry may change INR in people taking warfarin; UK warfarin labeling advises avoiding cranberry "
            "products."
        ),
        "sources": [f"{NCCIH}cranberry", UK_WARFARIN, pubmed("18516070"), pubmed("19553405")],
    })


def ginger_rule(sub: dict) -> None:
    assert sub["severity"] == "caution"
    sub.update({
        "evidence_level": "limited",
        "mechanism": (
            "In people taking warfarin, ginger use was associated with self-reported bleeding; a small single-dose "
            "study in healthy men found no change in INR or platelet aggregation. Evidence is limited and conflicting."
        ),
        "action": (
            "If you take a blood thinner, talk to your prescriber before using ginger supplements or concentrates, "
            "and report unusual bruising or bleeding."
        ),
        "alert_body": (
            "Ginger supplements may add to bleeding risk with blood thinners; the evidence is limited and "
            "conflicting. Talk to your prescriber before adding ginger and report unusual bruising or bleeding."
        ),
        "informational_note": "Ginger supplements may affect bleeding risk — relevant to people on anticoagulants.",
        "sources": [pubmed("17723077"), pubmed("15801937")],
    })


def fish_oil_rule(sub: dict) -> None:
    assert sub["severity"] == "monitor"
    sub.update({
        "mechanism": (
            "Omega-3 fatty acids (EPA/DHA) may prolong bleeding time. The prescription omega-3 label asks for "
            "periodic monitoring with drugs that affect coagulation; applying it to supplements and NSAIDs is an "
            "extrapolation."
        ),
        "action": (
            "If you take an NSAID regularly, mention omega-3 supplements to your clinician or pharmacist, especially "
            "if you have other bleeding risks."
        ),
        "sources": [LOVAZA, *sub["sources"]],
    })


# Same unsupported floor on the antiplatelet (bleeding) siblings: the agent's sibling fix, not Dr. Pham's decision.
SIBLING_EDITS = {
    ("RULE_IQM_GINKGO_HYPERTENSION", "antiplatelets"),
    ("RULE_INGREDIENT_GARLIC", "antiplatelets"),
}

RULE_EDITS = {
    ("RULE_INGREDIENT_ST_JOHNS_WORT", "anticoagulants"): sjw_rule,
    ("RULE_IQM_COQ10_HEART_DISEASE_STATINS", "anticoagulants"): coq10_rule,
    ("RULE_IQM_GINKGO_HYPERTENSION", "anticoagulants"): ginkgo_rule,
    ("RULE_IQM_GINKGO_HYPERTENSION", "antiplatelets"): ginkgo_antiplatelet_rule,
    ("RULE_INGREDIENT_GARLIC", "anticoagulants"): garlic_rule,
    ("RULE_INGREDIENT_GARLIC", "antiplatelets"): garlic_antiplatelet_rule,
    ("RULE_INGREDIENT_GLUCOSAMINE", "anticoagulants"): glucosamine_rule,
    ("RULE_INGREDIENT_CRANBERRY", "anticoagulants"): cranberry_rule,
    ("RULE_IQM_GINGER_BLEEDING", "anticoagulants"): ginger_rule,
    ("RULE_INGREDIENT_FISH_OIL", "nsaids"): fish_oil_rule,
}


def curated(blob: dict) -> None:
    done = set()
    for row in blob["interactions"]:
        if row["id"] in PAIRS:
            PAIRS[row["id"]](row)
            done.add(row["id"])
    assert done == set(PAIRS), set(PAIRS) - done


def rules(blob: dict) -> None:
    done = set()
    for rule in blob["interaction_rules"]:
        if rule["id"] == "RULE_INGREDIENT_GARLIC":
            drop_garlic_anticoagulant_tier(rule)
        for sub in rule.get("drug_class_rules", []):
            key = (rule["id"], sub["drug_class_id"])
            if key in RULE_EDITS:
                RULE_EDITS[key](sub)
                if key not in SIBLING_EDITS:
                    sub["clinical_review"] = dict(CLINICAL_REVIEW)
                done.add(key)
    assert done == set(RULE_EDITS), set(RULE_EDITS) - done


def edit(path: Path, fn) -> None:
    blob = data_batch.load(path)
    fn(blob)
    data_batch.save(path, blob)


def gold_cases(blob: dict, rules_blob: dict) -> None:
    """The two garlic gold cases pinned the removed 1200 mg tier; replace them with cases on live 3a gates so both
    evaluators (Python and the app's Dart copy) are checked on presence and on the DOAC exclusion."""
    def gate(rule_id: str, drug_class: str) -> dict:
        rule = next(r for r in rules_blob["interaction_rules"] if r["id"] == rule_id)
        return next(s for s in rule["drug_class_rules"] if s["drug_class_id"] == drug_class)["profile_gate"]

    def case(name, description, profile_gate, drug_classes, base, fires):
        return {
            "name": name,
            "description": description,
            "gate": profile_gate,
            "user_profile": {"conditions": [], "drug_classes": drug_classes, "profile_flags": []},
            "product_context": {"product_form": None, "nutrient_form": None, "dose_per_day": None, "dose_unit": None},
            "base_severity": base,
            "expected": {"fires": fires, "severity": base if fires else None},
        }

    cases = blob["test_cases"]
    old = {"gold_garlic_anticoagulant_above_threshold", "gold_garlic_anticoagulant_unknown_dose_uses_not_met_severity"}
    index = next(i for i, c in enumerate(cases) if c["name"] in old)
    cases[:] = [c for c in cases if c["name"] not in old]
    garlic = gate("RULE_INGREDIENT_GARLIC", "anticoagulants")
    sjw = gate("RULE_INGREDIENT_ST_JOHNS_WORT", "anticoagulants")
    cases[index:index] = [
        case("gold_garlic_anticoagulant_fires_without_a_dose",
             "Garlic with a blood thinner is caution on presence: no dose tier, an unknown amount still fires",
             garlic, ["anticoagulants"], "caution", True),
        case("gold_warfarin_only_gate_skips_a_doac_user",
             "Warfarin-specific St. John's wort evidence does not fire for a DOAC user",
             sjw, ["anticoagulants", "doacs"], "avoid", False),
        case("gold_warfarin_only_gate_keeps_an_unknown_blood_thinner",
             "Warfarin-specific evidence still fires when the blood thinner is not identified",
             sjw, ["anticoagulants"], "avoid", True),
    ]


def exemptions(blob: dict) -> None:
    # The rewritten ginger pair no longer mentions high-dose use; test_high_dose_rule_thresholds deletes stale entries.
    del blob["pairwise_interaction_ids"]["DSI_WAR_GINGER"]


if __name__ == "__main__":
    edit(CURATED, curated)
    edit(RULES, rules)
    edit(HIGH_DOSE_EXEMPTIONS, exemptions)
    rules_blob = data_batch.load(RULES)
    edit(GOLD_CASES, lambda blob: gold_cases(blob, rules_blob))
