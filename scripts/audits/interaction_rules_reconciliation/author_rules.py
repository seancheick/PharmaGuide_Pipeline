#!/usr/bin/env python3
"""Author the 5 reconciliation condition_rules into ingredient_interaction_rules.json.

Each condition_rule below is INDIVIDUALLY hand-authored from content-verified
sources (see research.md); this script only performs the JSON-safe insertion so
a 146-rule file is not hand-edited. Idempotent: re-running does not duplicate.
Run with --apply to write; default is a dry-run diff.

Sources content-verified 2026-07-04 (NIH ODS / NCCIH / ASRM + PMID-checked).
Retired (NOT authored, per user 2026-07-04): vitamin_d/kidney_disease,
zinc/kidney_disease — evidence says the app over-warns; drop the app entries.
"""
import argparse
import json
import sys
from pathlib import Path

RULES = Path(__file__).resolve().parents[2] / "data" / "ingredient_interaction_rules.json"
REVIEWED = "2026-07-04"


def _gate(condition_id, exclude_nutrient_forms=None):
    return {
        "gate_type": "condition",
        "requires": {"conditions_any": [condition_id], "drug_classes_any": [], "profile_flags_any": []},
        "excludes": {
            "conditions_any": [], "drug_classes_any": [], "profile_flags_any": [],
            "product_forms_any": [], "nutrient_forms_any": exclude_nutrient_forms or [],
        },
        "dose": None,
    }


# rule_id -> new condition_rule dict (appended to that rule's condition_rules)
NEW_CONDITION_RULES = {
    "RULE_IQM_VITAMIN_E_PREGNANCY_EXCESS": {
        "condition_id": "bleeding_disorders",
        "severity": "caution",
        "evidence_level": "probable",
        "last_reviewed": REVIEWED,
        "mechanism": "Vitamin E inhibits platelet aggregation and antagonizes vitamin K-dependent clotting factors. A meta-analysis of RCTs found a 22% increased risk of hemorrhagic stroke (Schurks 2010, pooled RR 1.22); the signal is anchored to ~400 IU/day supplemental doses and compounds with anticoagulant or antiplatelet use.",
        "action": "Use caution with supplemental vitamin E >=400 IU/day in bleeding disorders. Review with a clinician, especially if taking anticoagulants/antiplatelets or before surgery.",
        "sources": [
            "https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/",
            "https://pubmed.ncbi.nlm.nih.gov/21051774/",
        ],
        "alert_headline": "High-dose vitamin E may increase bleeding",
        "alert_body": "High-dose vitamin E (about 400 IU/day or more) can inhibit clotting and raise bleeding risk. If you have a bleeding disorder or take blood thinners, review vitamin E use with your clinician.",
        "informational_note": "Vitamin E can affect clotting at high doses — relevant to people with bleeding disorders.",
        "profile_gate": _gate("bleeding_disorders"),
        "direction": "harmful",
        "materiality": "dose_dependent",
        "min_effective_dose": {
            "value": 180, "unit": "mg", "basis": "per_day",
            "confidence": "medium", "confidence_basis": "trial_anchored_threshold",
            "source": "https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/",
            "rationale": "Hemorrhagic-stroke signal anchored to 400 IU/day synthetic (=180 mg) in Physicians' Health Study II (per NIH ODS); trace vitamin E in a multivitamin is far below this.",
        },
    },
    "RULE_INGREDIENT_GARLIC": {
        "condition_id": "bleeding_disorders",
        "severity": "caution",
        "evidence_level": "probable",
        "last_reviewed": REVIEWED,
        "mechanism": "Garlic inhibits platelet aggregation (allicin/ajoene antiplatelet activity). A 3-arm RCT found reduced platelet aggregation at 1200 and 2400 mg/day but NOT at 600 mg/day (Fakhar 2012). Case reports link garlic to surgical and spontaneous bleeding, compounded by anticoagulants/antiplatelets.",
        "action": "Use caution with garlic supplements >=1200 mg/day in bleeding disorders. Discontinue before surgery and review with a clinician if taking anticoagulants/antiplatelets.",
        "sources": [
            "https://www.nccih.nih.gov/health/garlic",
            "https://pubmed.ncbi.nlm.nih.gov/24575255/",
        ],
        "alert_headline": "Garlic supplements may increase bleeding",
        "alert_body": "Concentrated garlic supplements can reduce platelet clumping and raise bleeding risk, especially with blood thinners. If you have a bleeding disorder, review garlic use with your clinician.",
        "informational_note": "Garlic can affect clotting at supplement doses — relevant to people with bleeding disorders.",
        "profile_gate": _gate("bleeding_disorders"),
        "direction": "harmful",
        "materiality": "dose_dependent",
        "min_effective_dose": {
            "value": 1200, "unit": "mg", "basis": "per_day",
            "confidence": "medium", "confidence_basis": "rct_dose_ladder",
            "source": "https://pubmed.ncbi.nlm.nih.gov/24575255/",
            "rationale": "Antiplatelet effect seen at 1200 and 2400 mg/day but NOT at 600 mg/day in a 3-arm RCT (Fakhar 2012); culinary/trace garlic is below this.",
        },
    },
    "RULE_IQM_VITAMIN_B6_LACTATION": {
        "condition_id": "seizure_disorder",
        "severity": "caution",
        "evidence_level": "probable",
        "last_reviewed": REVIEWED,
        "mechanism": "High-dose pyridoxine can reduce serum concentrations of phenytoin and phenobarbital by increasing their metabolism (documented at 200 mg/day), potentially lowering seizure control. The neuropathy-based UL is 100 mg/day. RDA-level B6 has no antiepileptic interaction; several antiepileptic drugs actually deplete B6.",
        "action": "Use caution with pyridoxine >=100 mg/day in seizure disorders, particularly with phenytoin or phenobarbital. Review with a clinician; drug levels may need monitoring.",
        "sources": [
            "https://ods.od.nih.gov/factsheets/VitaminB6-HealthProfessional/",
            "https://www.ncbi.nlm.nih.gov/books/NBK554500/",
            "https://pubmed.ncbi.nlm.nih.gov/55569/",
        ],
        "alert_headline": "High-dose B6 may affect seizure medications",
        "alert_body": "High-dose vitamin B6 (100 mg/day or more) can lower blood levels of phenytoin and phenobarbital, reducing seizure control. If you take antiseizure medication, review B6 use with your clinician.",
        "informational_note": "High-dose B6 can affect some antiseizure drugs — relevant to people with a seizure disorder.",
        "profile_gate": _gate("seizure_disorder"),
        "direction": "harmful",
        "materiality": "dose_dependent",
        "min_effective_dose": {
            "value": 100, "unit": "mg", "basis": "per_day",
            "confidence": "medium", "confidence_basis": "conservative_ul",
            "source": "https://ods.od.nih.gov/factsheets/VitaminB6-HealthProfessional/",
            "rationale": "Phenytoin/phenobarbital serum-lowering documented at 200 mg/day; 100 mg/day (the neuropathy UL) is the conservative protective floor. RDA-level B6 has no AED interaction.",
        },
    },
    "RULE_INGREDIENT_CAFFEINE": {
        "condition_id": "ttc",
        "severity": "informational",
        "evidence_level": "limited",
        "last_reviewed": REVIEWED,
        "mechanism": "Fertility-specific evidence flags decreased fertility only at high intake (~500 mg/day; ASRM, OR 1.45). Moderate intake (1-2 cups, ~200 mg/day) has no apparent adverse effect on fertility. A 200 mg/day precautionary ceiling is borrowed from pregnancy guidance (ACOG) for those trying to conceive.",
        "action": "Moderate caffeine (under ~200 mg/day) is a reasonable precaution when trying to conceive; documented fertility concern is only at high intake (~500 mg/day).",
        "sources": [
            "https://www.asrm.org/practice-guidance/practice-committee-documents/optimizing-natural-fertility-a-committee-opinion-2021/",
            "https://pubmed.ncbi.nlm.nih.gov/20664420/",
        ],
        "alert_headline": "Consider moderating caffeine when trying to conceive",
        "alert_body": "Moderate caffeine (~200 mg/day, about 2 cups of coffee) has no clear fertility effect; only high intake (~500 mg/day) lowers fertility. Moderating caffeine is sensible when trying to conceive.",
        "informational_note": "Caffeine is a common preconception consideration — relevant to people trying to conceive.",
        "profile_gate": _gate("ttc"),
        "direction": "harmful",
        # dose_dependent (NOT presence): unlike the teratogens/contraindications in
        # the reproductive never-suppress bucket, moderate caffeine has no established
        # fertility effect (ASRM: 1-2 cups/day "no apparent adverse effects on
        # fertility"); the documented concern is ~500 mg/day. A precautionary 200 mg
        # floor with dose-suppression below it is evidence-based, not a fail-safe
        # violation. Explicitly exempted in test_never_suppress_buckets_are_presence.
        "materiality": "dose_dependent",
        "min_effective_dose": {
            "value": 200, "unit": "mg", "basis": "per_day",
            "confidence": "low", "confidence_basis": "precautionary_pregnancy_proxy",
            "source": "https://www.asrm.org/practice-guidance/practice-committee-documents/optimizing-natural-fertility-a-committee-opinion-2021/",
            "rationale": "Fertility harm documented only at ~500 mg/day (ASRM); 200 mg/day is a conservative precautionary floor borrowed from ACOG pregnancy guidance. Below this, no fertility concern.",
        },
    },
    # vitamin_a / ttc — INTENDED SEMANTICS (explicit, per review):
    #   BASE CAUTION at any dose of preformed retinol (materiality=presence,
    #   form-gated to exclude beta_carotene/mixed_carotenoids), ESCALATING to
    #   AVOID above 10,000 IU/day (the dose_thresholds entry below).
    # This is deliberately presence (NOT dose_dependent): preformed retinol is a
    # teratogen, and organogenesis occurs before pregnancy is usually confirmed
    # (Rothman: defects concentrated before the 7th week), so a preconception
    # user warrants a base caution at any dose — never dose-suppressed. Mirrors
    # the existing form-gated vitamin_a/pregnancy rule. (Contrast caffeine/ttc,
    # which IS dose_dependent because moderate caffeine is fertility-safe.)
    "RULE_IQM_VITAMIN_A_PREGNANCY_DOSE": {
        "condition_id": "ttc",
        "severity": "caution",
        "evidence_level": "established",
        "last_reviewed": REVIEWED,
        "mechanism": "Preformed vitamin A (retinol/retinyl esters) is teratogenic in early pregnancy, which can occur before conception is confirmed; the apparent threshold is ~10,000 IU/day (Rothman 1995, RR 4.8, ~1 in 57 attributable malformations). Beta-carotene is not teratogenic. Cranial-neural-crest development occurs before the 7th week, so the preconception window mirrors pregnancy.",
        "action": "When trying to conceive, keep supplemental preformed vitamin A (retinol) within prenatal range (<10,000 IU/day). Beta-carotene is preferred. Discuss with a clinician.",
        "sources": [
            "https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/",
            "https://pubmed.ncbi.nlm.nih.gov/7477116/",
        ],
        "alert_headline": "Keep preformed vitamin A moderate when trying to conceive",
        "alert_body": "High-dose preformed vitamin A (retinol, 10,000 IU/day or more) can affect early pregnancy, even before it's detected. Beta-carotene is fine. Keep retinol in prenatal range when trying to conceive.",
        "informational_note": "Preformed retinol is dose-sensitive before conception — relevant to people trying to conceive.",
        "profile_gate": _gate("ttc", exclude_nutrient_forms=["beta_carotene", "mixed_carotenoids"]),
        "direction": "harmful",
        "materiality": "presence",
    },
}

# Additional condition_rules for rules that already appear above (a dict can't
# key the same rule twice). Surfaced by the reconciliation audit: surgery/vitamin_e
# is a genuine app-only suppression (vitamin E antiplatelet -> perioperative
# bleeding), sibling of the bleeding_disorders rule, mirroring garlic (which has
# both bleeding_disorders and surgery_scheduled).
ADDITIONAL_CONDITION_RULES = [
    ("RULE_IQM_VITAMIN_E_PREGNANCY_EXCESS", {
        "condition_id": "surgery_scheduled",
        "severity": "caution",
        "evidence_level": "probable",
        "last_reviewed": REVIEWED,
        "mechanism": "Vitamin E inhibits platelet aggregation and antagonizes vitamin K-dependent clotting factors, raising perioperative bleeding risk at high supplemental doses (~400 IU/day and above).",
        "action": "Discontinue high-dose vitamin E (>=400 IU/day) 1-2 weeks before scheduled surgery; review with the surgical team.",
        "sources": [
            "https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/",
            "https://pubmed.ncbi.nlm.nih.gov/21051774/",
        ],
        "alert_headline": "Stop high-dose vitamin E before surgery",
        "alert_body": "High-dose vitamin E can increase bleeding. If you have surgery scheduled, ask your clinician about stopping vitamin E supplements about 1-2 weeks beforehand.",
        "informational_note": "Vitamin E can increase bleeding — relevant before scheduled surgery.",
        "profile_gate": _gate("surgery_scheduled"),
        "direction": "harmful",
        "materiality": "dose_dependent",
        "min_effective_dose": {
            "value": 180, "unit": "mg", "basis": "per_day",
            "confidence": "medium", "confidence_basis": "trial_anchored_threshold",
            "source": "https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/",
            "rationale": "Same antiplatelet/hemorrhagic mechanism as the bleeding_disorders rule (400 IU/day = 180 mg synthetic, per NIH ODS); standard advice is to discontinue before surgery.",
        },
    }),
]

# vitamin_a / ttc also needs a dose_thresholds escalation entry (mirror pregnancy).
NEW_DOSE_THRESHOLDS = {
    "RULE_IQM_VITAMIN_A_PREGNANCY_DOSE": {
        "scope": "condition",
        "target_id": "ttc",
        "basis": "per_day",
        "comparator": ">",
        "value": 10000,
        "unit": "iu",
        "severity_if_met": "avoid",
        "severity_if_not_met": "caution",
        "profile_gate": {
            "gate_type": "combination",
            "requires": {"conditions_any": ["ttc"], "drug_classes_any": [], "profile_flags_any": []},
            "excludes": {
                "conditions_any": [], "drug_classes_any": [], "profile_flags_any": [],
                "product_forms_any": [], "nutrient_forms_any": ["beta_carotene", "mixed_carotenoids"],
            },
            "dose": {"basis": "per_day", "comparator": ">", "value": 10000, "unit": "iu",
                     "severity_if_met": "avoid", "severity_if_not_met": "caution"},
        },
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    args = ap.parse_args()

    data = json.loads(RULES.read_text())
    by_id = {r.get("id"): r for r in data["interaction_rules"]}
    added = 0

    for rid, cr in NEW_CONDITION_RULES.items():
        rule = by_id.get(rid)
        if rule is None:
            print(f"  !! rule {rid} not found — ABORT")
            sys.exit(1)
        crs = rule.setdefault("condition_rules", [])
        existing = next((x for x in crs if x.get("condition_id") == cr["condition_id"]), None)
        if existing == cr:
            print(f"  = {rid} / {cr['condition_id']} already present, unchanged (idempotent skip)")
            continue
        if existing is not None:
            crs[crs.index(existing)] = cr
            print(f"  ~ {rid} / {cr['condition_id']} REPLACED ({cr['direction']}/{cr['materiality']}, sev={cr['severity']})")
        else:
            crs.append(cr)
            print(f"  + {rid} / {cr['condition_id']}  ({cr['direction']}/{cr['materiality']}, sev={cr['severity']})")
        added += 1

    for rid, cr in ADDITIONAL_CONDITION_RULES:
        rule = by_id.get(rid)
        crs = rule.setdefault("condition_rules", [])
        existing = next((x for x in crs if x.get("condition_id") == cr["condition_id"]), None)
        if existing == cr:
            print(f"  = {rid} / {cr['condition_id']} already present, unchanged (idempotent skip)")
            continue
        if existing is not None:
            crs[crs.index(existing)] = cr
            print(f"  ~ {rid} / {cr['condition_id']} REPLACED ({cr['direction']}/{cr['materiality']}, sev={cr['severity']})")
        else:
            crs.append(cr)
            print(f"  + {rid} / {cr['condition_id']}  ({cr['direction']}/{cr['materiality']}, sev={cr['severity']})")
        added += 1

    for rid, dt in NEW_DOSE_THRESHOLDS.items():
        rule = by_id.get(rid)
        dts = rule.setdefault("dose_thresholds", [])
        if any(x.get("target_id") == dt["target_id"] and x.get("scope") == dt["scope"] for x in dts):
            print(f"  = {rid} dose_threshold[{dt['target_id']}] already present (idempotent skip)")
            continue
        dts.append(dt)
        print(f"  + {rid} dose_threshold[{dt['target_id']}] >{dt['value']} {dt['unit']} -> {dt['severity_if_met']}")

    meta = data.setdefault("_metadata", {})
    meta["last_updated"] = REVIEWED

    if args.apply:
        # ensure_ascii=True to match the file's existing serialization (739 \u
        # escapes) so the diff shows ONLY the intended additions, not escape churn.
        RULES.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")
        print(f"\nAPPLIED: {added} condition_rules written to {RULES.name}")
    else:
        print(f"\nDRY-RUN: would add {added} condition_rules. Re-run with --apply.")


if __name__ == "__main__":
    main()
