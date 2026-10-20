#!/usr/bin/env python3
"""Add RULE_BOTAN_STAR_ANISE_SEIZURE (receipts: research.md in this folder).

Run once from the repo root: $PG_PYTHON scripts/audits/interaction_rules/star_anise_2026_10/apply.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

PATH = REPO / "scripts" / "data" / "ingredient_interaction_rules.json"
REVIEW_PATH = REPO / "scripts" / "data" / "interaction_rules_ghost_review.json"
FDA_ADVISORY = "https://web.archive.org/web/20050115085515/http://www.fda.gov/bbs/topics/NEWS/2003/NEW00941.html"
EMPTY_EXCLUDES = {"conditions_any": [], "drug_classes_any": [], "profile_flags_any": [],
                  "product_forms_any": [], "nutrient_forms_any": []}

RULE = {
    "id": "RULE_BOTAN_STAR_ANISE_SEIZURE",
    "subject_ref": {"db": "botanical_ingredients", "canonical_id": "star_anise"},
    "condition_rules": [{
        "condition_id": "seizure_disorder",
        "severity": "caution",
        "evidence_level": "limited",
        "mechanism": (
            "Chinese star anise (Illicium verum) can be contaminated with or mistaken for Japanese "
            "star anise (Illicium anisatum), whose neurotoxin anisatin can cause seizures; dried, the "
            "two cannot be told apart by eye. In 2003 FDA linked star anise teas to about 40 illnesses, "
            "including seizures, and advised against drinking them. A 2004 case series described 7 "
            "infants with neurologic reactions after star anise tea and found evidence that Chinese "
            "star anise had been contaminated with Japanese star anise."
        ),
        "action": (
            "If you have epilepsy or another seizure disorder, talk to your doctor before using star "
            "anise. Stop using it and get medical care if you notice seizures, jitteriness, rapid eye "
            "movements or vomiting."
        ),
        "sources": [
            FDA_ADVISORY,
            "https://pubmed.ncbi.nlm.nih.gov/15492355/",
            "https://pubmed.ncbi.nlm.nih.gov/22484123/",
        ],
        "alert_headline": "Possible contamination linked to seizures",
        "alert_body": (
            "Star anise can be mixed with toxic Japanese star anise, which has caused seizures. If you "
            "have epilepsy or a seizure disorder, talk to your doctor before using it."
        ),
        "informational_note": (
            "Star anise can be contaminated with Japanese star anise, a neurotoxic species linked to "
            "seizures."
        ),
        "profile_gate": {
            "gate_type": "condition",
            "requires": {"conditions_any": ["seizure_disorder"], "drug_classes_any": [],
                         "profile_flags_any": []},
            "excludes": dict(EMPTY_EXCLUDES),
            "dose": None,
        },
        "direction": "harmful",
        "materiality": "presence",
        "last_reviewed": "2026-10-20",
    }],
    "drug_class_rules": [],
    "dose_thresholds": [],
    "pregnancy_lactation": {
        "pregnancy_category": "no_data",
        "lactation_category": "no_data",
        "evidence_level": "no_data",
        "notes": ("Pregnancy and breastfeeding safety data for star anise supplements are limited; "
                  "discuss use with your clinician."),
        "alert_headline": "Limited safety data",
        "alert_body": ("There isn't enough specific safety data to give a confident recommendation "
                       "for pregnancy or breastfeeding. Talk to your obstetrician or pediatrician "
                       "before using this supplement."),
        "informational_note": ("Pregnancy/lactation safety data is limited — clinician guidance "
                               "recommended."),
        "direction": "unknown",
        "materiality": "presence",
    },
    "last_reviewed": "2026-10-20",
    "review_owner": "Source-content review (agent), 2026-10-20; not clinician-reviewed",
}


# The strict citation gate's topic check reads title/abstract/MeSH for a seizure stem.
REVIEW = {
    "pmid": "15492355",
    "rule_id": "RULE_BOTAN_STAR_ANISE_SEIZURE",
    "sub_rule": "condition:seizure_disorder",
    "live_title": "Neurotoxicities in infants seen with the consumption of star anise tea.",
    "rationale": (
        "Heuristic miss: cited only for what the abstract states, 7 infants with adverse neurologic "
        "reactions after star anise tea and evidence that Chinese star anise was contaminated with "
        "Japanese star anise (MeSH Neurotoxicity Syndromes, Food Contamination). The seizure claim "
        "rests on the FDA advisory and PMID 22484123 (anisatin causes epilepsy), which the gate finds."
    ),
    "reviewed_by": "agent source-content review (not clinician-reviewed)",
    "reviewed_at": "2026-10-20",
}


def main() -> None:
    blob = data_batch.load(PATH)
    rules = blob["interaction_rules"]
    assert not any(r["id"] == RULE["id"] for r in rules), "already applied"
    assert not any(r["subject_ref"] == RULE["subject_ref"] for r in rules), "one rule per subject"
    rules.append(RULE)
    if "total_rules" in blob["_metadata"]:
        blob["_metadata"]["total_rules"] = len(rules)
    print(data_batch.save(PATH, blob))

    review = data_batch.load(REVIEW_PATH)
    keys = {(r["pmid"], r["rule_id"], r["sub_rule"]) for r in review["reviewed"]}
    assert (REVIEW["pmid"], REVIEW["rule_id"], REVIEW["sub_rule"]) not in keys
    review["reviewed"].append(REVIEW)
    print(data_batch.save(REVIEW_PATH, review))


if __name__ == "__main__":
    main()
