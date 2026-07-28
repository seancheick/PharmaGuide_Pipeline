#!/usr/bin/env python3
"""Prepare the four B1.1 candidates for a bounded pharmacist delta review.

This script deliberately does not promote a record to ``verified``. It authors
the evidence-aligned proposal, keeps every candidate consumer-hidden, and
writes an immutable proposal ledger for the licensed-pharmacist delta review.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[3]
DATA = ROOT / "scripts" / "data"
SOURCE_PATH = DATA / "medication_depletions.json"
CLASSES_PATH = DATA / "drug_classes.json"
EXPECTATIONS_PATH = DATA / "medication_depletion_citation_expectations.json"
LEDGER_PATH = DATA / "medication_depletions_b1_1_signoff.json"

REVIEW_DATE = "2026-07-27"
REVIEWER = "b1_1_evidence_audit"

CANDIDATE_IDS = (
    "DEP_ANTACIDS_VITAMINB12",
    "DEP_ANTACIDS_MAGNESIUM",
    "DEP_DIURETICS_POTASSIUM",
    "DEP_DIURETICS_MAGNESIUM",
)

PROPOSAL_FIELDS = (
    "id",
    "drug_ref",
    "depleted_nutrient",
    "depletion_type",
    "severity",
    "mechanism",
    "clinical_impact",
    "recommendation",
    "onset_timeline",
    "evidence_level",
    "monitoring_note",
    "sources",
    "alert_headline",
    "alert_body",
    "acknowledgement_note",
    "monitoring_tip_short",
    "food_sources_short",
    "citation_review_status",
    "reviewed_at",
    "reviewer",
    "citation_review_note",
)

PRILOSEC_LABEL = (
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
    "setid=b6761f84-53ac-4745-a8c8-1e5427d7e179"
)
FUROSEMIDE_LABEL = (
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
    "setid=f3173c0d-2b62-7c7b-e053-2995a90ada05"
)
HCTZ_LABEL = (
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
    "setid=8a1de4e2-3aca-a4d3-e053-2995a90a1a41"
)


def _source(source_type: str, label: str, url: str) -> dict[str, str]:
    return {"source_type": source_type, "label": label, "url": url}


def _proposal_fingerprint(record: dict[str, Any]) -> str:
    payload = json.dumps(
        {field: record.get(field) for field in PROPOSAL_FIELDS},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _class_fingerprint(drug_class: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "member_rxcuis": drug_class.get("member_rxcuis", []),
            "member_names": drug_class.get("member_names", []),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _apply_candidates(by_id: dict[str, dict[str, Any]]) -> None:
    b12 = by_id["DEP_ANTACIDS_VITAMINB12"]
    b12.update(
        {
            "drug_ref": {
                "type": "class",
                "id": "class:proton_pump_inhibitors",
                "display_name": "Proton pump inhibitors (PPIs)",
            },
            "depletion_type": "depletion",
            "severity": "moderate",
            "mechanism": (
                "PPIs reduce gastric acid. With prolonged use, this can impair "
                "absorption of food-bound vitamin B12; the degree of effect "
                "varies, and observational studies do not show that every user "
                "becomes deficient."
            ),
            "clinical_impact": (
                "Long-term PPI use is associated with a modestly higher "
                "likelihood of vitamin B12 deficiency, but the literature is "
                "heterogeneous and association does not prove causation. "
                "Confirmed deficiency can contribute to anemia or neurologic symptoms."
            ),
            "recommendation": (
                "Do not start high-dose B12 solely because you take a PPI. If "
                "use is prolonged or you have anemia, neurologic symptoms, a "
                "restricted diet, or other B12 risk factors, ask your clinician "
                "whether B12 testing is appropriate; treat confirmed deficiency "
                "with an individualized plan."
            ),
            "onset_timeline": "years",
            "evidence_level": "probable",
            "monitoring_note": (
                "Routine testing for every PPI user is not established. "
                "Consider symptom- and risk-based B12 assessment during prolonged therapy."
            ),
            "sources": [
                _source(
                    "nih_ods",
                    "NIH ODS — Vitamin B12 Fact Sheet for Health Professionals",
                    "https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/",
                ),
                _source(
                    "pubmed",
                    (
                        "Lam JR et al. Proton pump inhibitor and histamine 2 "
                        "receptor antagonist use and vitamin B12 deficiency. "
                        "JAMA. 2013;310(22):2435-42"
                    ),
                    "https://pubmed.ncbi.nlm.nih.gov/24327038/",
                ),
                _source(
                    "pubmed",
                    (
                        "Choudhury A et al. Vitamin B12 deficiency and use of "
                        "proton pump inhibitors: a systematic review and "
                        "meta-analysis. Expert Rev Gastroenterol Hepatol. "
                        "2023;17(5):479-487"
                    ),
                    "https://pubmed.ncbi.nlm.nih.gov/37060552/",
                ),
                _source(
                    "fda",
                    (
                        "DailyMed — PRILOSEC (omeprazole) prescribing "
                        "information, sections 5.8 and 5.9"
                    ),
                    PRILOSEC_LABEL,
                ),
            ],
            "alert_headline": "Long-term PPI use may affect vitamin B12",
            "alert_body": (
                "With long-term PPI use, reduced stomach acid may lower "
                "absorption of vitamin B12 from food. Not everyone develops low levels."
            ),
            "acknowledgement_note": (
                "You're already considering B12 intake; testing and individual "
                "factors still guide whether treatment is needed."
            ),
            "monitoring_tip_short": (
                "Ask whether B12 testing fits if use is prolonged or anemia, "
                "nerve symptoms, or other factors appear."
            ),
            "food_sources_short": (
                "Vitamin B12 is found in animal foods and fortified foods; "
                "laboratory assessment helps evaluate absorption and intake."
            ),
            "citation_review_status": "needs_revision",
            "reviewed_at": REVIEW_DATE,
            "reviewer": REVIEWER,
            "citation_review_note": (
                "B1.1 evidence revision completed. PPI-only scope retained; "
                "FDA labeling, a large observational study, and a heterogeneous "
                "2023 meta-analysis support cautious long-term B12 wording. "
                "Blanket 1,000 mcg/day advice and the retired food-versus-"
                "supplement claim were removed. The record remains suppressed "
                "pending licensed pharmacist delta review."
            ),
        }
    )
    b12.pop("adequacy_threshold_mcg", None)
    b12.pop("adequacy_threshold_mg", None)

    ppi_magnesium = by_id["DEP_ANTACIDS_MAGNESIUM"]
    ppi_magnesium.update(
        {
            "drug_ref": {
                "type": "class",
                "id": "class:proton_pump_inhibitors",
                "display_name": "Proton pump inhibitors (PPIs)",
            },
            "depletion_type": "depletion",
            "severity": "significant",
            "mechanism": (
                "Rare PPI-associated hypomagnesemia appears to involve reduced "
                "intestinal magnesium absorption, but the precise molecular "
                "mechanism is not established. Dechallenge and rechallenge "
                "reports support a PPI class effect."
            ),
            "clinical_impact": (
                "Low magnesium may be asymptomatic or can contribute to tetany, "
                "seizures, or arrhythmias and may accompany low calcium or "
                "potassium. FDA labeling notes that some cases required "
                "magnesium replacement and stopping the PPI."
            ),
            "recommendation": (
                "Do not start a routine magnesium dose solely because you take "
                "a PPI. For prolonged therapy—especially with digoxin, a "
                "diuretic, or other risk factors—ask whether baseline and "
                "periodic magnesium testing is appropriate. Management of a "
                "low result should be clinician-directed."
            ),
            "onset_timeline": "variable",
            "evidence_level": "established",
            "monitoring_note": (
                "FDA labeling advises considering magnesium before and "
                "periodically during prolonged PPI therapy, especially with "
                "digoxin or medicines that can lower magnesium."
            ),
            "sources": [
                _source(
                    "pubmed",
                    (
                        "Hess MW et al. Systematic review: hypomagnesaemia "
                        "induced by proton pump inhibition. Aliment Pharmacol "
                        "Ther. 2012;36(5):405-13"
                    ),
                    "https://pubmed.ncbi.nlm.nih.gov/22762246/",
                ),
                _source(
                    "fda",
                    (
                        "DailyMed — PRILOSEC (omeprazole) prescribing "
                        "information, section 5.9"
                    ),
                    PRILOSEC_LABEL,
                ),
            ],
            "alert_headline": "Rarely, long-term PPIs may lower magnesium",
            "alert_body": (
                "With prolonged use, PPIs can rarely lower magnesium. Most "
                "reports follow a year or more of use, but cases have occurred earlier."
            ),
            "acknowledgement_note": (
                "You're already tracking magnesium intake; laboratory results "
                "and your treatment plan guide any needed changes."
            ),
            "monitoring_tip_short": (
                "Ask whether magnesium monitoring fits prolonged PPI use, "
                "especially with digoxin or a diuretic."
            ),
            "food_sources_short": (
                "Food sources of magnesium include leafy greens, nuts, seeds, "
                "whole grains, and beans."
            ),
            "citation_review_status": "needs_revision",
            "reviewed_at": REVIEW_DATE,
            "reviewer": REVIEWER,
            "citation_review_note": (
                "B1.1 evidence revision completed. The live FDA label and PMID "
                "22762246 support a rare PPI class effect with a broad reported "
                "onset range, so the proposal now uses variable onset and "
                "acknowledges earlier cases. The dead FDA URL and blanket "
                "200–400 mg/day advice remain removed. The record remains "
                "suppressed pending licensed pharmacist delta review."
            ),
        }
    )
    ppi_magnesium.pop("adequacy_threshold_mcg", None)
    ppi_magnesium.pop("adequacy_threshold_mg", None)

    potassium = by_id["DEP_DIURETICS_POTASSIUM"]
    potassium.update(
        {
            "drug_ref": {
                "type": "class",
                "id": "class:loop_and_thiazide_diuretics",
                "display_name": "Loop and thiazide diuretics (water pills)",
            },
            "depletion_type": "depletion",
            "severity": "significant",
            "mechanism": (
                "Loop and thiazide diuretics increase renal sodium delivery "
                "and urinary electrolyte losses. This can lower potassium; the "
                "likelihood depends on the agent, dose, intake, kidney "
                "function, and concurrent medications."
            ),
            "clinical_impact": (
                "Low potassium can cause muscle weakness or cramps and increase "
                "arrhythmia risk; it can also increase digoxin toxicity. Some "
                "patients do not develop low potassium, and kidney disease or "
                "other medicines can instead raise it."
            ),
            "recommendation": (
                "Do not start potassium or deliberately increase dietary "
                "potassium without checking with your prescriber. Serum "
                "potassium should be monitored; any food, supplement, or "
                "prescription replacement plan must account for kidney "
                "function and other medications."
            ),
            "onset_timeline": "variable",
            "evidence_level": "established",
            "monitoring_note": (
                "Monitor serum potassium at intervals chosen for the specific "
                "diuretic, dose, kidney function, intercurrent illness, and "
                "interacting medicines."
            ),
            "sources": [
                _source(
                    "fda",
                    "DailyMed — Furosemide tablets prescribing information",
                    FUROSEMIDE_LABEL,
                ),
                _source(
                    "fda",
                    (
                        "DailyMed — Hydrochlorothiazide tablets prescribing "
                        "information"
                    ),
                    HCTZ_LABEL,
                ),
            ],
            "alert_headline": "Loop and thiazide diuretics may lower potassium",
            "alert_body": (
                "With regular use or after dose changes, loop and thiazide "
                "diuretics can lower potassium. The effect varies and "
                "laboratory monitoring guides management."
            ),
            "acknowledgement_note": (
                "Confirm any potassium product\u2014including over-the-counter\u2014"
                "with your prescriber; the right amount depends on your labs."
            ),
            "monitoring_tip_short": (
                "Ask how often potassium should be checked based on the "
                "diuretic, dose, kidneys, and other medicines."
            ),
            "food_sources_short": (
                "Potassium is found in potatoes, beans, fruit, dairy, and "
                "vegetables; whether to change intake depends on labs and kidney function."
            ),
            "citation_review_status": "needs_revision",
            "reviewed_at": REVIEW_DATE,
            "reviewer": REVIEWER,
            "citation_review_note": (
                "B1.1 evidence revision completed. Current furosemide and "
                "hydrochlorothiazide labels support hypokalemia and electrolyte "
                "monitoring across the existing loop/thiazide-only class. "
                "Blanket 20–40 mEq/day advice was removed and potassium-sparing "
                "agents remain excluded. The record remains suppressed pending "
                "licensed pharmacist delta review."
            ),
        }
    )
    potassium.pop("adequacy_threshold_mcg", None)
    potassium.pop("adequacy_threshold_mg", None)

    diuretic_magnesium = by_id["DEP_DIURETICS_MAGNESIUM"]
    diuretic_magnesium.update(
        {
            "drug_ref": {
                "type": "class",
                "id": "class:loop_and_thiazide_diuretics",
                "display_name": "Loop and thiazide diuretics (water pills)",
            },
            "depletion_type": "depletion",
            "severity": "moderate",
            "mechanism": (
                "Loop and thiazide diuretics can increase urinary magnesium "
                "losses through their effects on renal electrolyte handling. "
                "The magnitude and mechanism differ by diuretic subclass and "
                "by individual clinical factors."
            ),
            "clinical_impact": (
                "Low magnesium can contribute to weakness, cramps, tremor, or "
                "arrhythmias and can coexist with low potassium. The finding "
                "requires clinical interpretation because symptoms and risk "
                "also depend on kidney function and other medicines."
            ),
            "recommendation": (
                "Do not start a routine magnesium dose solely because you take "
                "a diuretic. Ask whether magnesium should be included with "
                "electrolyte monitoring, especially if potassium is low, "
                "symptoms appear, the dose is high, or intake is limited; "
                "correction should be clinician-directed."
            ),
            "onset_timeline": "variable",
            "evidence_level": "established",
            "monitoring_note": (
                "Use periodic or more frequent electrolyte monitoring according "
                "to the specific agent, dose, kidney function, symptoms, and "
                "other medicines; include magnesium when clinically relevant."
            ),
            "sources": [
                _source(
                    "fda",
                    "DailyMed — Furosemide tablets prescribing information",
                    FUROSEMIDE_LABEL,
                ),
                _source(
                    "fda",
                    (
                        "DailyMed — Hydrochlorothiazide tablets prescribing "
                        "information"
                    ),
                    HCTZ_LABEL,
                ),
                _source(
                    "pubmed",
                    (
                        "Ellison DH. Divalent cation transport by the distal "
                        "nephron: insights from Bartter's and Gitelman's "
                        "syndromes. Am J Physiol Renal Physiol. "
                        "2000;279(4):F616-25"
                    ),
                    "https://pubmed.ncbi.nlm.nih.gov/10997911/",
                ),
            ],
            "alert_headline": "Loop and thiazide diuretics may lower magnesium",
            "alert_body": (
                "With regular use, loop and thiazide diuretics can increase "
                "urinary magnesium loss. The likelihood varies by medicine, "
                "dose, and individual factors."
            ),
            "acknowledgement_note": (
                "You're already considering magnesium intake; lab results and "
                "your treatment plan determine whether changes are needed."
            ),
            "monitoring_tip_short": (
                "Ask whether magnesium should be checked with other "
                "electrolytes, especially if potassium is low."
            ),
            "food_sources_short": (
                "Food sources of magnesium include leafy greens, nuts, seeds, "
                "whole grains, and beans."
            ),
            "citation_review_status": "needs_revision",
            "reviewed_at": REVIEW_DATE,
            "reviewer": REVIEWER,
            "citation_review_note": (
                "B1.1 evidence revision completed. Current furosemide and "
                "hydrochlorothiazide labels support hypomagnesemia/urinary "
                "magnesium loss across the existing loop/thiazide-only class; "
                "PMID 10997911 supports the subclass-aware mechanism. The mouse "
                "cell PMID 9083264 and blanket 200–400 mg/day advice were "
                "removed. The record remains suppressed pending licensed "
                "pharmacist delta review."
            ),
        }
    )
    diuretic_magnesium.pop("adequacy_threshold_mcg", None)
    diuretic_magnesium.pop("adequacy_threshold_mg", None)


def _update_metadata(source: dict[str, Any]) -> None:
    metadata = source["_metadata"]
    metadata["last_updated"] = REVIEW_DATE
    migration = {
        "from": metadata["schema_version"],
        "to": metadata["schema_version"],
        "date": REVIEW_DATE,
        "summary": (
            "B1.1 candidate preparation: evidence-aligned PPI B12/magnesium "
            "and loop/thiazide potassium/magnesium copy; all four remain "
            "suppressed pending licensed-pharmacist delta sign-off."
        ),
    }
    completed = metadata["migration"]["completed_migrations"]
    if migration not in completed:
        completed.append(migration)
    metadata["onset_timeline_values"] = (
        "days, weeks, months, years, or variable when source labeling does not "
        "support a single fixed onset."
    )


def _update_expectations(payload: dict[str, Any]) -> None:
    candidate_expectations = [
        {
            "entry_id": "DEP_ANTACIDS_VITAMINB12",
            "pmid": "24327038",
            "expected": {
                "drug_terms_any": [
                    "proton pump inhibitor",
                    "PPIs",
                    "acid-suppressing medication",
                ],
                "nutrient_terms_any": ["vitamin B12", "B12"],
                "context_terms_any": ["2 or more years", "long-term"],
            },
            "reviewer_disposition": "candidate_for_pharmacist_review",
        },
        {
            "entry_id": "DEP_ANTACIDS_VITAMINB12",
            "pmid": "37060552",
            "expected": {
                "drug_terms_any": ["proton pump inhibitor", "PPI"],
                "nutrient_terms_any": ["vitamin B12", "B12"],
                "context_terms_any": ["systematic review", "meta-analysis"],
            },
            "reviewer_disposition": "candidate_for_pharmacist_review",
        },
        {
            "entry_id": "DEP_ANTACIDS_MAGNESIUM",
            "pmid": "22762246",
            "expected": {
                "drug_terms_any": ["proton pump inhibitor", "PPIs"],
                "nutrient_terms_any": ["hypomagnesaemia", "magnesium"],
                "context_terms_any": ["long-term", "drug-class effect"],
            },
            "reviewer_disposition": "candidate_for_pharmacist_review",
        },
        {
            "entry_id": "DEP_DIURETICS_MAGNESIUM",
            "pmid": "10997911",
            "expected": {
                "drug_terms_any": ["loop diuretics", "thiazide diuretics"],
                "nutrient_terms_any": ["magnesium", "hypomagnesemia"],
                "context_terms_any": ["urinary excretion", "chronic effects"],
            },
            "reviewer_disposition": "candidate_for_pharmacist_review",
        },
    ]
    kept = [
        item
        for item in payload["expectations"]
        if item.get("entry_id") not in CANDIDATE_IDS
    ]
    payload["expectations"] = kept + candidate_expectations
    payload["_metadata"]["last_updated"] = REVIEW_DATE
    payload["_metadata"]["total_entries"] = len(payload["expectations"])


def _build_ledger(
    by_id: dict[str, dict[str, Any]],
    classes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    notes = {
        "DEP_ANTACIDS_VITAMINB12": (
            "Confirm the PPI-only scope, probable evidence tier, and "
            "symptom/risk-based testing language."
        ),
        "DEP_ANTACIDS_MAGNESIUM": (
            "Confirm the rare but potentially clinically important signal, "
            "variable onset, and risk-based monitoring language."
        ),
        "DEP_DIURETICS_POTASSIUM": (
            "Confirm the loop/thiazide-only scope, variable timing, and the "
            "explicit no-self-supplementation safety language."
        ),
        "DEP_DIURETICS_MAGNESIUM": (
            "Confirm the subclass-aware mechanism, variable timing, and "
            "clinician-directed monitoring/correction language."
        ),
    }
    return {
        "_metadata": {
            "schema_version": "5.5.0",
            "description": (
                "Machine-enforced B1.1 four-candidate proposal and pending "
                "licensed-pharmacist delta-review state."
            ),
            "purpose": "medication_depletion_clinical_change_control",
            "total_entries": 3,
            "reviewed_at": REVIEW_DATE,
            "candidate_count": len(CANDIDATE_IDS),
            "evidence_reviewer": REVIEWER,
            "supporting_reviewer": REVIEWER,
            "supporting_reviewer_type": "AI clinical-content audit",
            "reviewer": "",
            "reviewer_type": "Licensed pharmacist clinical review requested",
            "licensed_pharmacist_signoff": False,
            "licensed_pharmacist_signoff_date": None,
            "licensed_clinical_approver_organization": (
                "PharmaGuide Clinical Team"
            ),
            "release_disposition": "pending_licensed_pharmacist_delta_review",
            "packet_title": "B1.1 pharmacist delta review packet",
            "packet_status": (
                "evidence revision complete; licensed pharmacist sign-off requested"
            ),
            "packet_scope": (
                "4 suppressed B1.1 candidates; none are consumer-visible "
                "until separately approved. They are separate from the "
                "reopened B1 active-copy delta."
            ),
        },
        "records": {
            entry_id: {
                "disposition": "pending_licensed_pharmacist_review",
                "note": notes[entry_id],
            }
            for entry_id in CANDIDATE_IDS
        },
        "candidate_record_fingerprints": {
            entry_id: _proposal_fingerprint(by_id[entry_id])
            for entry_id in CANDIDATE_IDS
        },
        "candidate_class_fingerprints": {
            class_id: _class_fingerprint(classes[class_id])
            for class_id in (
                "class:loop_and_thiazide_diuretics",
                "class:proton_pump_inhibitors",
            )
        },
    }


def main() -> int:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    by_id = {record["id"]: record for record in source["depletions"]}
    missing = sorted(set(CANDIDATE_IDS) - set(by_id))
    if missing:
        raise SystemExit(f"missing B1.1 candidates: {missing}")

    _apply_candidates(by_id)
    _update_metadata(source)
    SOURCE_PATH.write_text(
        json.dumps(source, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )

    expectations = json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))
    _update_expectations(expectations)
    EXPECTATIONS_PATH.write_text(
        json.dumps(expectations, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )

    classes = json.loads(CLASSES_PATH.read_text(encoding="utf-8"))["classes"]
    ledger = _build_ledger(by_id, classes)
    LEDGER_PATH.write_text(
        json.dumps(ledger, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Prepared 4 B1.1 candidates; all remain suppressed pending licensed "
        "pharmacist delta review."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
