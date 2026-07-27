#!/usr/bin/env python3
"""Apply the bounded final B1 clinical-content review.

This audit intentionally fails closed on medication scopes the runtime cannot
represent.  It also writes the immutable sign-off ledger consumed by the B1
change-control release test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[3]
DATA_PATH = ROOT / "scripts/data/medication_depletions.json"
CLASSES_PATH = ROOT / "scripts/data/drug_classes.json"
LEDGER_PATH = ROOT / "scripts/data/medication_depletions_b1_signoff.json"

REVIEW_DATE = "2026-07-27"
REVIEWER = "openai_codex_ai_clinical_audit"

CLINICAL_FIELDS = (
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
    "citation_review_status",
    "reviewed_at",
    "reviewer",
    "citation_review_note",
    "b1_clinical_review_disposition",
    "b1_clinical_reviewed_at",
    "b1_clinical_reviewer",
    "b1_clinical_review_note",
)

APPROVED = {
    "DEP_ANTICONVULSANTS_CALCIUM": "Evidence, inducer scope, and bone-health wording align.",
    "DEP_ANTICONVULSANTS_FOLATE": "Phenytoin-specific evidence and supplement caution align.",
    "DEP_ANTICONVULSANTS_VITAMINB12": "Phenytoin-specific meta-analysis supports the cautious monitoring claim.",
    "DEP_ANTICONVULSANTS_VITAMIND": "Carbamazepine-specific meta-analysis supports the bounded claim.",
    "DEP_CHOLESTYRAMINE_VITAMINA": "Current prescribing information supports reduced fat-soluble vitamin absorption.",
    "DEP_CHOLESTYRAMINE_VITAMIND": "Current prescribing information supports reduced fat-soluble vitamin absorption.",
    "DEP_CHOLESTYRAMINE_VITAMINE": "Current prescribing information supports reduced fat-soluble vitamin absorption.",
    "DEP_CHOLESTYRAMINE_VITAMINK": "Current prescribing information supports reduced fat-soluble vitamin absorption.",
    "DEP_DIURETICS_CALCIUM": "Loop-diuretic calciuria and cautious bone-health wording align.",
    "DEP_DIURETICS_FOLATE": "Triamterene-specific antifolate evidence and risk-qualified wording align.",
    "DEP_ISONIAZID_VITAMINB6": "Current label and systematic review support the clinician-directed B6 recommendation.",
    "DEP_LEVOTHYROXINE_IRON": "Direct interaction evidence and four-hour separation advice align.",
    "DEP_ORLISTAT_VITAMINA": "Current XENICAL label supports daily ADEK multivitamin separation.",
    "DEP_ORLISTAT_VITAMIND": "Current XENICAL label supports daily ADEK multivitamin separation.",
    "DEP_ORLISTAT_VITAMINE": "Current XENICAL label supports daily ADEK multivitamin separation.",
    "DEP_ORLISTAT_VITAMINK": "Current XENICAL label supports daily ADEK multivitamin separation.",
    "DEP_STATINS_COQ10": "Blood-level reduction is established and the copy preserves uncertain clinical significance.",
    "DEP_SULFASALAZINE_FOLATE": "Current label supports impaired folate absorption/metabolism and clinician direction.",
}

REVISED = {
    "DEP_ANTACIDS_CALCIUM": "Reclassified as monitoring rather than body-calcium depletion; retained the bounded carbonate/fracture evidence.",
    "DEP_ANTACIDS_IRON": "Aligned onset and monitoring advice with the >=2-year clinical evidence; removed unsupported dose-separation advice.",
    "DEP_ANTICOAGULANTS_VITAMINK": "Narrowed the overbroad anticoagulant class to warfarin and removed speculative bone/vascular outcomes.",
    "DEP_ANTICONVULSANTS_LCARNITINE": "Downgraded severity and made the small pediatric evidence/routine-supplement uncertainty explicit.",
    "DEP_COLCHICINE_VITAMINB12": "Kept the recognized malabsorption signal but removed any implication of universal periodic screening.",
    "DEP_CORTICOSTEROIDS_CALCIUM": "Narrowed the route-ambiguous class to long-term oral prednisone and retained guideline-directed bone care.",
    "DEP_CORTICOSTEROIDS_VITAMIND": "Narrowed the route-ambiguous class to long-term oral prednisone and retained monitoring-only wording.",
    "DEP_DIURETICS_THIAMINE": "Separated direct urinary loss from heart-failure confounding and removed any routine-supplement implication.",
    "DEP_DIURETICS_ZINC": "Removed an unsupported 10-15 mg/day supplement suggestion; retained the mild thiazide urinary-loss signal.",
    "DEP_LEVOTHYROXINE_CALCIUM": "Limited four-hour separation advice to calcium supplements/products rather than ordinary calcium-rich meals.",
    "DEP_METFORMIN_VITAMINB12": "Aligned mechanism, monitoring, and treatment wording with NIH, MHRA, and ADA 2026 guidance.",
    "DEP_METHOTREXATE_FOLATE": "Explicitly separated low-dose inflammatory-disease folate support from oncology/rescue protocols.",
    "DEP_SSRIS_SODIUM": "Made the SIADH mechanism and monitoring timing appropriately non-categorical.",
}

NONAPPROVED = {
    "DEP_OCP_VITAMINB6": {
        "disposition": "requires_evidence_revision",
        "status": "needs_revision",
        "note": (
            "The source concerns estrogen-containing oral contraceptives, but "
            "the runtime class includes implants, injectable progestins, "
            "emergency contraception, and non-contraceptive megestrol. Keep "
            "suppressed until a reliably normalized combined-oral scope and "
            "independent clinical-importance evidence exist."
        ),
    },
    "DEP_ANTICONVULSANTS_VITAMINK": {
        "disposition": "remove_from_release",
        "status": "rejected",
        "note": (
            "The later review does not support routine antenatal vitamin K, "
            "the signal is pregnancy-specific, and the runtime has no "
            "pregnancy context. A significant class-wide consumer warning "
            "would be a false positive outside pregnancy."
        ),
    },
}


def _sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _record_fingerprint(record: dict[str, Any]) -> str:
    return _sha256({field: record.get(field) for field in CLINICAL_FIELDS})


def _class_fingerprint(drug_class: dict[str, Any]) -> str:
    return _sha256(
        {
            "member_rxcuis": drug_class.get("member_rxcuis", []),
            "member_names": drug_class.get("member_names", []),
        }
    )


def _touch_citation_review(record: dict[str, Any], note: str) -> None:
    record["reviewed_at"] = REVIEW_DATE
    record["reviewer"] = REVIEWER
    record["citation_review_note"] = note


def _append_source(record: dict[str, Any], source: dict[str, str]) -> None:
    for item in record["sources"]:
        if item.get("url") == source["url"]:
            item.update(source)
            return
    record["sources"].append(source)


def _apply_copy_and_scope(by_id: dict[str, dict[str, Any]]) -> None:
    calcium = by_id["DEP_ANTACIDS_CALCIUM"]
    calcium.update(
        {
            "depletion_type": "monitoring_stability",
            "mechanism": (
                "PPIs reduce stomach acid. In fasting studies this can reduce "
                "absorption of insoluble calcium carbonate; calcium citrate is "
                "less acid-dependent, and taking carbonate with food improves "
                "absorption. This does not establish whole-body calcium deficiency."
            ),
            "clinical_impact": (
                "Long-term PPI use is associated in observational studies with "
                "a modestly higher fracture risk, but confounding remains and "
                "the association does not prove calcium deficiency."
            ),
            "recommendation": (
                "Do not start calcium solely because you take a PPI. Aim for "
                "adequate dietary calcium and vitamin D. If a clinician "
                "recommends calcium, ask whether calcium citrate or calcium "
                "carbonate taken with food fits your situation."
            ),
            "alert_headline": "Long-term PPI use can affect calcium planning",
            "alert_body": (
                "With long-term use, PPIs can reduce fasting absorption of "
                "calcium carbonate, but they do not automatically cause calcium deficiency."
            ),
            "acknowledgement_note": (
                "You're considering calcium intake thoughtfully; the amount "
                "that fits depends on diet and individual bone-health needs."
            ),
            "monitoring_tip_short": (
                "For long-term PPI use, discuss calcium intake and bone risk "
                "rather than self-starting a dose."
            ),
        }
    )

    iron = by_id["DEP_ANTACIDS_IRON"]
    iron.update(
        {
            "onset_timeline": "years",
            "clinical_impact": (
                "Use for two years or longer is associated with a higher risk "
                "of iron deficiency, with greater risk at higher doses and "
                "longer duration. Other causes of iron deficiency still need "
                "clinical evaluation."
            ),
            "recommendation": (
                "If you use a PPI or H2 blocker long term and have iron-deficiency "
                "symptoms or risk factors, ask your clinician whether ferritin "
                "and blood-count testing is appropriate. Do not start iron "
                "without confirming the cause and a suitable treatment plan."
            ),
            "alert_headline": "Long-term acid suppression can affect iron status",
            "alert_body": (
                "PPI or H2-blocker use for two years or longer is associated "
                "with a higher chance of iron deficiency, especially at higher doses."
            ),
            "monitoring_tip_short": (
                "Discuss ferritin and blood-count testing if long-term use "
                "coincides with symptoms or other iron-deficiency risks."
            ),
        }
    )

    metformin = by_id["DEP_METFORMIN_VITAMINB12"]
    metformin.update(
        {
            "mechanism": (
                "Metformin can reduce vitamin B12 absorption through a "
                "multifactorial process. Reduced calcium-dependent uptake of "
                "the intrinsic-factor–B12 complex in the ileum is one proposed "
                "mechanism, but it is not the only established explanation."
            ),
            "clinical_impact": (
                "The chance of low vitamin B12 rises with higher metformin dose, "
                "longer treatment, and other B12 risk factors. Deficiency can "
                "cause anemia or neuropathy, which can be mistaken for diabetic "
                "neuropathy."
            ),
            "recommendation": (
                "Periodic vitamin B12 assessment should be considered during "
                "long-term metformin therapy, especially after about 4–5 years, "
                "at higher doses, with other B12 risk factors, or with anemia "
                "or neuropathy. Treat a confirmed deficiency using a "
                "clinician-directed regimen; do not stop metformin on your own."
            ),
            "alert_headline": "Long-term metformin can lower vitamin B12",
            "alert_body": (
                "With long-term use, the chance of low B12 rises with higher "
                "doses and other B12 factors. Symptoms and low results need clinical evaluation."
            ),
            "acknowledgement_note": (
                "You're addressing B12 thoughtfully; treatment can be tailored "
                "to your test results and clinician's plan."
            ),
            "monitoring_tip_short": (
                "Consider B12 testing with long-term use, anemia, neuropathy, "
                "or other B12 risk factors."
            ),
        }
    )
    _append_source(
        metformin,
        {
            "source_type": "reference",
            "label": (
                "American Diabetes Association. Standards of Care in "
                "Diabetes—2026, recommendation 3.10"
            ),
            "url": (
                "https://diabetesjournals.org/care/article/49/Supplement_1/"
                "S50/163924/3-Prevention-or-Delay-of-Diabetes-and-Associated"
            ),
        },
    )
    _append_source(
        metformin,
        {
            "source_type": "reference",
            "label": (
                "MHRA. Metformin and reduced vitamin B12 levels: "
                "new advice for monitoring patients at risk. 2022."
            ),
            "url": (
                "https://www.gov.uk/drug-safety-update/metformin-and-reduced-"
                "vitamin-b12-levels-new-advice-for-monitoring-patients-at-risk"
            ),
        },
    )

    zinc = by_id["DEP_DIURETICS_ZINC"]
    zinc.update(
        {
            "recommendation": (
                "Routine zinc supplementation is not established solely "
                "because you take a thiazide. Aim for zinc-rich foods; if you "
                "have symptoms or additional deficiency risks, discuss whether "
                "testing or supplementation is appropriate."
            ),
            "acknowledgement_note": (
                "Diet usually covers zinc needs during thiazide therapy; more "
                "is not automatically better."
            ),
            "monitoring_tip_short": (
                "Consider zinc evaluation only when symptoms or additional "
                "deficiency risks are present."
            ),
        }
    )

    thiamine = by_id["DEP_DIURETICS_THIAMINE"]
    thiamine.update(
        {
            "mechanism": (
                "Furosemide increases urinary thiamine loss largely by "
                "increasing urine flow. Studies in heart failure also report "
                "low thiamine status, although illness severity and dietary "
                "intake can contribute."
            ),
            "clinical_impact": (
                "Lower thiamine status is most plausible with chronic, "
                "higher-dose furosemide and additional risks such as heart "
                "failure or poor intake. The evidence does not establish "
                "deficiency in every person taking furosemide."
            ),
            "recommendation": (
                "With chronic higher-dose furosemide, poor intake, or symptoms "
                "compatible with deficiency, ask the treating clinician whether "
                "thiamine assessment or supplementation is appropriate. Do not "
                "change the diuretic on your own."
            ),
            "alert_body": (
                "Furosemide increases urinary thiamine loss. Clinical relevance "
                "is greatest with long-term higher doses and other deficiency risks."
            ),
        }
    )

    prednisone_ref = {
        "type": "drug",
        "id": "8640",
        "display_name": "Long-term oral prednisone",
    }
    steroid_calcium = by_id["DEP_CORTICOSTEROIDS_CALCIUM"]
    steroid_calcium.update(
        {
            "drug_ref": prednisone_ref,
            "mechanism": (
                "Long-term oral prednisone can reduce intestinal calcium "
                "absorption, increase urinary calcium loss, reduce bone "
                "formation, and increase bone resorption. The concern is bone "
                "strength rather than a measurable fall in blood calcium."
            ),
            "clinical_impact": (
                "Prednisone taken for more than three months at about "
                "2.5 mg/day or more raises osteoporosis and fracture risk. "
                "Short courses are not represented by this record."
            ),
            "recommendation": (
                "For prednisone expected to continue longer than three months, "
                "clinicians assess calcium and vitamin D intake, fracture risk, "
                "and whether bone-protective treatment is needed. Care is based "
                "on individual risk rather than an automatic supplement dose."
            ),
            "alert_headline": "Long-term oral prednisone can affect calcium balance",
            "alert_body": (
                "Oral prednisone used for more than three months can affect "
                "calcium balance and bone strength."
            ),
        }
    )
    steroid_vitamin_d = by_id["DEP_CORTICOSTEROIDS_VITAMIND"]
    steroid_vitamin_d.update(
        {
            "drug_ref": prednisone_ref.copy(),
            "mechanism": (
                "Long-term oral prednisone increases bone loss and fracture "
                "risk, so vitamin D status and intake are considered during "
                "bone-health management. Evidence does not show that prednisone "
                "reliably drains vitamin D itself."
            ),
            "clinical_impact": (
                "Vitamin D matters as part of bone protection during prednisone "
                "therapy lasting more than three months, not because every user "
                "develops vitamin D deficiency."
            ),
            "recommendation": (
                "If oral prednisone is expected to continue longer than three "
                "months, ask the treating clinician whether vitamin D intake, "
                "testing, and fracture-risk assessment are appropriate. There "
                "is no universal supplement dose."
            ),
            "alert_headline": "Long-term oral prednisone needs bone-health planning",
            "alert_body": (
                "With long-term oral prednisone, vitamin D is considered as "
                "part of bone care; the drug does not automatically cause deficiency."
            ),
        }
    )

    ssri = by_id["DEP_SSRIS_SODIUM"]
    ssri.update(
        {
            "mechanism": (
                "SSRIs are associated with SIADH and dilutional hyponatremia, "
                "in which excess water lowers blood sodium. Serotonergic effects "
                "on antidiuretic hormone are proposed, but the exact mechanism "
                "is not fully established."
            ),
            "clinical_impact": (
                "Risk is highest soon after starting or increasing an SSRI and "
                "in older adults, people taking thiazide diuretics, and those "
                "with prior hyponatremia. Severe hyponatremia can cause marked "
                "confusion, seizures, or reduced consciousness."
            ),
            "recommendation": (
                "If you have hyponatremia risk factors, your prescriber may "
                "check sodium at baseline and during early treatment. Report "
                "new nausea, headache, unsteadiness, or confusion promptly; "
                "seizures or reduced consciousness require urgent care. This "
                "is not treated by self-supplementing sodium."
            ),
            "alert_headline": "SSRIs can rarely lower blood sodium",
            "alert_body": (
                "Over time, especially in the first weeks of treatment, risk is "
                "greater with older age, thiazide use, or prior low sodium."
            ),
            "monitoring_tip_short": (
                "Ask whether early sodium monitoring fits your risk factors; "
                "report new symptoms promptly."
            ),
        }
    )

    carnitine = by_id["DEP_ANTICONVULSANTS_LCARNITINE"]
    carnitine.update(
        {
            "severity": "moderate",
            "mechanism": (
                "Long-term valproate can reduce carnitine availability and "
                "alter fatty-acid oxidation. The cited supplementation study "
                "was small and conducted in children, so it does not establish "
                "routine deficiency or treatment for every valproate user."
            ),
            "clinical_impact": (
                "Carnitine depletion is most relevant in children and people "
                "with risk factors such as poor nutrition, metabolic disease, "
                "multiple antiseizure medicines, or suspected valproate toxicity. "
                "Acute toxicity is a separate urgent-care situation."
            ),
            "recommendation": (
                "Do not start carnitine routinely from this alert. Discuss risk "
                "factors, symptoms, and whether testing or supplementation is "
                "appropriate with the clinician managing valproate."
            ),
            "alert_headline": "Valproate can affect carnitine in higher-risk use",
            "alert_body": (
                "With long-term valproate, the clearest concern is in children "
                "and people with additional clinical factors; supplementation is not universal."
            ),
        }
    )
    _append_source(
        carnitine,
        {
            "source_type": "pubmed",
            "label": (
                "Raskind JY, El-Chaar GM. The role of carnitine "
                "supplementation during valproic acid therapy. Ann Pharmacother. 2000."
            ),
            "url": "https://pubmed.ncbi.nlm.nih.gov/10852092/",
        },
    )

    levothyroxine_calcium = by_id["DEP_LEVOTHYROXINE_CALCIUM"]
    levothyroxine_calcium.update(
        {
            "mechanism": (
                "Calcium supplements and calcium-containing medicines can bind "
                "levothyroxine in the gastrointestinal tract and reduce its "
                "absorption. This affects thyroid-drug bioavailability rather "
                "than depleting body calcium stores."
            ),
            "recommendation": (
                "Take calcium supplements or calcium-containing medicines at "
                "least four hours before or after levothyroxine. If you start, "
                "stop, or change their timing, ask your clinician whether "
                "thyroid testing is needed."
            ),
            "alert_body": (
                "Over time, calcium supplements taken close to levothyroxine "
                "can reduce thyroid-medicine absorption."
            ),
        }
    )
    levothyroxine_label = {
        "source_type": "reference",
        "label": (
            "DailyMed — Levothyroxine Sodium prescribing information "
            "(calcium and iron separation)"
        ),
        "url": (
            "https://www.dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?"
            "setid=a0dbd009-0a3e-4314-812f-dd372c255bb1&type=display"
        ),
    }
    _append_source(levothyroxine_calcium, levothyroxine_label)
    _append_source(by_id["DEP_LEVOTHYROXINE_IRON"], levothyroxine_label)

    warfarin = by_id["DEP_ANTICOAGULANTS_VITAMINK"]
    warfarin.update(
        {
            "drug_ref": {
                "type": "drug",
                "id": "11289",
                "display_name": "Warfarin (anticoagulant / blood thinner)",
            },
            "mechanism": (
                "Warfarin inhibits vitamin K epoxide reductase (VKORC1), "
                "reducing the recycling of vitamin K needed to activate clotting "
                "factors II, VII, IX, and X and proteins C and S. This is "
                "warfarin's intended drug action, not dietary vitamin K deficiency."
            ),
            "clinical_impact": (
                "Large or sudden changes in vitamin K intake can change the INR "
                "and make warfarin less or more anticoagulant, increasing clotting "
                "or bleeding risk. Consistency matters more than avoiding "
                "vitamin K-rich foods."
            ),
            "recommendation": (
                "Keep vitamin K intake reasonably consistent. Contact the "
                "warfarin prescriber or anticoagulation service before starting "
                "or stopping vitamin K supplements or making a major dietary "
                "change; do not change warfarin on your own."
            ),
            "monitoring_note": (
                "INR monitoring frequency and follow-up after diet, supplement, "
                "or medication changes should be set by the anticoagulation team."
            ),
            "alert_headline": "Warfarin is sensitive to vitamin K changes",
            "alert_body": (
                "Over time, warfarin intentionally blocks vitamin K recycling; "
                "sudden diet or supplement changes can shift the INR."
            ),
            "acknowledgement_note": (
                "A reasonably consistent vitamin K intake supports steadier "
                "warfarin control."
            ),
        }
    )
    _append_source(
        warfarin,
        {
            "source_type": "reference",
            "label": (
                "DailyMed — Warfarin Sodium prescribing information "
                "(consistent vitamin K intake)"
            ),
            "url": (
                "https://dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?"
                "setid=801e4da1-5459-47d2-b67b-009f0a3247cc&type=display"
            ),
        },
    )

    methotrexate = by_id["DEP_METHOTREXATE_FOLATE"]
    methotrexate.update(
        {
            "mechanism": (
                "Methotrexate is an antifolate medicine. With low-dose regimens "
                "for inflammatory disease, clinician-prescribed folic or folinic "
                "acid can reduce folate-mediated adverse effects. Oncology and "
                "rescue regimens use different folate protocols."
            ),
            "clinical_impact": (
                "In low-dose inflammatory-disease treatment, appropriate folate "
                "support can reduce mouth sores, nausea, liver-enzyme elevations, "
                "cytopenias, and treatment discontinuation. The schedule cannot "
                "be generalized to cancer treatment."
            ),
            "recommendation": (
                "Use only the folic-acid or folinic-acid schedule prescribed "
                "for your exact methotrexate regimen. Do not start, stop, or "
                "retime folate without the rheumatology, dermatology, gastroenterology, "
                "or oncology prescriber."
            ),
            "alert_body": (
                "With regular use, folate support is common for low-dose "
                "methotrexate in inflammatory disease, but oncology regimens differ."
            ),
        }
    )

    colchicine = by_id["DEP_COLCHICINE_VITAMINB12"]
    colchicine.update(
        {
            "clinical_impact": (
                "Long-term colchicine can contribute to low B12 in susceptible "
                "people, but modern evidence does not establish deficiency or "
                "routine screening in every user. Symptoms and other B12 risks "
                "should guide evaluation."
            ),
            "recommendation": (
                "If long-term colchicine use coincides with anemia, neuropathy "
                "symptoms, or other B12 risk factors, ask whether B12 testing is "
                "appropriate. Routine supplementation is not established solely "
                "because colchicine is prescribed."
            ),
            "alert_body": (
                "Long-term colchicine may reduce B12 absorption in susceptible "
                "people; this does not mean every user becomes deficient."
            ),
        }
    )


def main() -> int:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    classes = json.loads(CLASSES_PATH.read_text(encoding="utf-8"))["classes"]
    by_id = {record["id"]: record for record in data["depletions"]}

    review_scope = set(APPROVED) | set(REVISED) | set(NONAPPROVED)
    if len(review_scope) != 33:
        raise RuntimeError(f"Expected 33 review records, found {len(review_scope)}")
    missing = review_scope - set(by_id)
    if missing:
        raise RuntimeError(f"Missing review records: {sorted(missing)}")

    _apply_copy_and_scope(by_id)

    records: dict[str, dict[str, str]] = {}
    for record_id, note in APPROVED.items():
        record = by_id[record_id]
        disposition = "approved"
        record["b1_clinical_review_disposition"] = disposition
        record["b1_clinical_reviewed_at"] = REVIEW_DATE
        record["b1_clinical_reviewer"] = REVIEWER
        record["b1_clinical_review_note"] = note
        records[record_id] = {"disposition": disposition, "note": note}

    for record_id, note in REVISED.items():
        record = by_id[record_id]
        disposition = "approved_with_wording_change"
        record["b1_clinical_review_disposition"] = disposition
        record["b1_clinical_reviewed_at"] = REVIEW_DATE
        record["b1_clinical_reviewer"] = REVIEWER
        record["b1_clinical_review_note"] = note
        _touch_citation_review(record, note)
        records[record_id] = {"disposition": disposition, "note": note}

    for record_id, review in NONAPPROVED.items():
        record = by_id[record_id]
        disposition = review["disposition"]
        record["citation_review_status"] = review["status"]
        record["b1_clinical_review_disposition"] = disposition
        record["b1_clinical_reviewed_at"] = REVIEW_DATE
        record["b1_clinical_reviewer"] = REVIEWER
        record["b1_clinical_review_note"] = review["note"]
        _touch_citation_review(record, review["note"])
        records[record_id] = {
            "disposition": disposition,
            "note": review["note"],
        }

    data["_metadata"]["last_updated"] = REVIEW_DATE
    DATA_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    active = {
        record["id"]: record
        for record in data["depletions"]
        if record.get("citation_review_status") == "verified"
    }
    active_class_ids = sorted(
        {
            record["drug_ref"]["id"]
            for record in active.values()
            if record["drug_ref"]["type"] == "class"
        }
    )
    ledger = {
        "_metadata": {
            "schema_version": "5.4.0",
            "description": (
                "Machine-enforced final B1 clinical-content dispositions and "
                "active record/class fingerprints."
            ),
            "purpose": "medication_depletion_clinical_change_control",
            # Universal data-file metadata counts the three top-level payload
            # dictionaries; the clinical scope count is recorded separately.
            "total_entries": 3,
            "reviewed_at": REVIEW_DATE,
            "review_scope_count": len(review_scope),
            "active_record_count": len(active),
            "reviewer": REVIEWER,
            "reviewer_type": "AI clinical-content audit",
            "licensed_pharmacist_signoff": False,
            "release_disposition": "approved_for_controlled_beta",
            "change_control": (
                "Any active record, active class membership, citation, or "
                "promotion change requires evidence review and ledger regeneration."
            ),
        },
        "records": dict(sorted(records.items())),
        "active_record_fingerprints": {
            record_id: _record_fingerprint(record)
            for record_id, record in sorted(active.items())
        },
        "active_class_fingerprints": {
            class_id: _class_fingerprint(classes[class_id])
            for class_id in active_class_ids
        },
    }
    LEDGER_PATH.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        f"Reviewed {len(review_scope)} records; "
        f"{len(active)} remain active; wrote {LEDGER_PATH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
