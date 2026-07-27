#!/usr/bin/env python3
"""Section 3 — antiseizure medication relationships, made mechanism-specific.

Seven DEP_ANTICONVULSANTS_* records were attributed to ``class:anticonvulsants``
(40 members spanning CYP inducers, a CYP inhibitor, and renally-cleared drugs).
Each record's own mechanism prose already named the real actors.  This moves the
attribution onto the prose, splitting by the two mechanisms that actually exist,
and suppresses the one record whose evidence does not support shipping.  The
follow-up content audit also narrows evidence that is direct only for
carbamazepine or phenytoin; a class label must never out-run its citation.

Idempotent: re-running makes no further change.  Every rxcui below was verified
live against RxNorm on 2026-07-26.

    python3 scripts/audits/section_03_antiseizure/apply.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
CLASSES_PATH = DATA / "drug_classes.json"
DEPLETIONS_PATH = DATA / "medication_depletions.json"

INDUCERS = "class:enzyme_inducing_antiseizure_medications"
VALPROATE = "class:valproate"

INDUCER_DISPLAY = "Enzyme-inducing antiseizure medications"
VALPROATE_DISPLAY = "Valproate (valproic acid, divalproex / Depakote)"

# RxNorm-verified 2026-07-26. One moiety, four dispensed forms — the salt on the
# label must not decide whether the patient is warned.
VALPROATE_CLASS = {
    "display_name": "Valproate (valproic acid, divalproex / Depakote)",
    "description": (
        "The valproate moiety across its dispensed salts. Pharmacologically the "
        "opposite of the enzyme-inducing antiseizure drugs: valproate INHIBITS "
        "CYP450, so it causes none of the induction-driven depletions (vitamin D, "
        "vitamin K, calcium, folate) and has its own L-carnitine risk through "
        "acylcarnitine conjugation. The biotin signal remains suppressed pending "
        "valproate-specific evidence."
    ),
    "member_rxcuis": ["266856", "9919", "40254", "11118"],
    "member_names": ["divalproex sodium", "sodium valproate", "valproate", "valproic acid"],
    "rxclass_id": "N03AG01",
    "atc_codes": ["N03AG01"],
    "notes": (
        "Valproate moiety across its dispensed salts (Depakote is divalproex). "
        "Deliberately separate from class:enzyme_inducing_antiseizure_medications: "
        "valproate INHIBITS CYP450, so it shares none of the induction-driven "
        "depletions (vitamin D, vitamin K, calcium, folate). It carries its own "
        "L-carnitine risk through acylcarnitine conjugation. The biotin signal is "
        "suppressed pending valproate-specific evidence. All 4 rxcuis "
        "content-verified against RxNorm 2026-07-26."
    ),
}

# (entry_id, new drug_ref id, new display_name)
REATTRIBUTIONS = [
    ("DEP_ANTICONVULSANTS_CALCIUM", INDUCERS, INDUCER_DISPLAY),
    ("DEP_ANTICONVULSANTS_VITAMINK", INDUCERS, INDUCER_DISPLAY),
    ("DEP_ANTICONVULSANTS_LCARNITINE", VALPROATE, VALPROATE_DISPLAY),
]

# Prose that named drugs now outside the record's scope.  Changing a drug_ref
# without changing the text it contradicts is how stale wording reaches the app.
TEXT_REWRITES = {
    "DEP_ANTICONVULSANTS_VITAMIND": {
        "drug_ref": {"type": "drug", "id": "2002", "display_name": "Carbamazepine"},
        "mechanism": "Long-term carbamazepine treatment is associated with lower circulating 25-hydroxyvitamin D. Carbamazepine is an enzyme-inducing antiseizure medication; this record does not generalize that result to every antiseizure medicine.",
        "clinical_impact": "Lower vitamin D can contribute to poorer bone health over time. Individual fracture risk and treatment decisions need clinical assessment.",
        "recommendation": "Discuss vitamin D intake and whether testing is appropriate with the clinician managing carbamazepine. Do not start high-dose vitamin D without individualized advice.",
        "monitoring_note": "A clinician can decide whether 25-hydroxyvitamin D testing is appropriate based on duration of treatment and bone-health risk factors.",
        "sources": [{"source_type": "pubmed", "label": "Impact of carbamazepine on vitamin D levels: A meta-analysis. Epilepsy Res. 2021.", "url": "https://pubmed.ncbi.nlm.nih.gov/34847425/"}],
        "alert_headline": "Carbamazepine may lower vitamin D over time",
        "alert_body": "Long-term carbamazepine use has been associated with lower vitamin D levels. Your clinician can help decide whether testing or treatment is needed.",
        "acknowledgement_note": "Vitamin D intake is one part of bone-health planning during long-term carbamazepine therapy.",
        "monitoring_tip_short": "Ask whether vitamin D testing fits your treatment plan.",
        "citation_review_status": "verified",
        "reviewed_at": "2026-07-26",
        "reviewer": "medication_depletion_section_03_content_audit",
        "citation_review_note": "Section 3 content audit: PMID 34847425 is a carbamazepine-specific meta-analysis of lower 25-hydroxyvitamin D. The record is direct-drug scoped; no class-wide inference is shipped.",
    },
    "DEP_ANTICONVULSANTS_CALCIUM": {
        "mechanism": "Anticonvulsant-associated bone disease can involve increased bone remodeling. Reduced vitamin D and lower calcium intake are relevant clinical considerations; this record is limited to the reviewed enzyme-inducing subset.",
        "clinical_impact": "Long-term treatment can be associated with bone-health concerns. The appropriate evaluation depends on individual fracture and osteoporosis risk.",
        "recommendation": "Discuss dietary calcium, vitamin D, and bone-health risk with the clinician managing long-term enzyme-inducing antiseizure treatment rather than self-prescribing a dose.",
        "monitoring_note": "A clinician can decide whether calcium, vitamin D, or bone evaluation is appropriate for the individual.",
        "sources": [{"source_type": "pubmed", "label": "Treatment of anticonvulsant drug-induced bone disease. Epilepsy Behav. 2004.", "url": "https://pubmed.ncbi.nlm.nih.gov/15123011/"}],
        "alert_body": "Long-term enzyme-inducing antiseizure treatment can be relevant to bone health. Calcium and vitamin D plans should be individualized with a clinician.",
        "acknowledgement_note": "Calcium intake is one part of bone-health planning during long-term treatment.",
        "monitoring_tip_short": "Discuss calcium and vitamin D in the context of your bone-health risk.",
        "citation_review_status": "verified",
        "reviewed_at": "2026-07-26",
        "reviewer": "medication_depletion_section_03_content_audit",
        "citation_review_note": "Section 3 content audit: PMID 15123011 reviews anticonvulsant-associated bone disease and calcium intake. Copy is limited to bone-health discussion, not a universal supplement dose.",
    },
    "DEP_ANTICONVULSANTS_FOLATE": {
        "drug_ref": {"type": "drug", "id": "8183", "display_name": "Phenytoin"},
        "mechanism": "Long-term phenytoin therapy can lower folate status. Several mechanisms have been proposed, but this record is limited to phenytoin rather than generalized to all antiseizure medicines.",
        "clinical_impact": "Low folate can contribute to megaloblastic anemia. In people who could become pregnant, folate planning should be discussed with the prescribing clinician.",
        "recommendation": "Discuss folate intake and any supplement dose with the clinician managing phenytoin. Folate supplementation can affect phenytoin concentrations in some people, so self-directed high doses are not appropriate.",
        "monitoring_note": "A clinician can decide whether folate and CBC testing is appropriate and coordinate any supplement plan with seizure control.",
        "sources": [{"source_type": "pubmed", "label": "Phenytoin-folic acid: a review. Drug Intell Clin Pharm. 1984.", "url": "https://pubmed.ncbi.nlm.nih.gov/6370643/"}],
        "alert_headline": "Phenytoin may lower folate over time",
        "alert_body": "Long-term phenytoin use can lower folate status. Discussing folate with your prescribing clinician is especially important when planning pregnancy.",
        "acknowledgement_note": "Folate planning should be coordinated with phenytoin treatment.",
        "monitoring_tip_short": "Ask whether folate testing or supplementation fits your plan.",
        "citation_review_status": "verified",
        "reviewed_at": "2026-07-26",
        "reviewer": "medication_depletion_section_03_content_audit",
        "citation_review_note": "Section 3 content audit: PMID 6370643 is a phenytoin-folate review. The record is direct-drug scoped and avoids unsupported claims for other antiseizure medicines.",
    },
    "DEP_ANTICONVULSANTS_VITAMINB12": {
        "drug_ref": {"type": "drug", "id": "8183", "display_name": "Phenytoin"},
        "mechanism": "A systematic review and meta-analysis found lower serum vitamin B12 in people receiving phenytoin monotherapy. The mechanism is not established, so this record does not attribute the effect to other antiseizure medicines.",
        "clinical_impact": "Low vitamin B12 can contribute to anemia or neurologic symptoms, but deficiency should be confirmed and evaluated clinically.",
        "recommendation": "Discuss whether vitamin B12 testing is appropriate with the clinician managing long-term phenytoin. Treatment should follow an identified deficiency or individualized clinical advice.",
        "evidence_level": "probable",
        "monitoring_note": "A clinician can decide whether vitamin B12 and related testing is appropriate for long-term phenytoin therapy.",
        "sources": [{"source_type": "pubmed", "label": "Effects of phenytoin on serum levels of homocysteine, vitamin B12, folate in patients with epilepsy: a systematic review and meta-analysis. Medicine (Baltimore). 2019.", "url": "https://pubmed.ncbi.nlm.nih.gov/30896627/"}],
        "alert_headline": "Phenytoin may lower vitamin B12 over time",
        "alert_body": "Over years of phenytoin treatment, studies have associated monotherapy with lower vitamin B12. Your clinician can help decide whether testing is useful.",
        "acknowledgement_note": "Vitamin B12 planning can be discussed as part of long-term phenytoin care.",
        "monitoring_tip_short": "Ask whether vitamin B12 testing fits your treatment plan.",
        "citation_review_status": "verified",
        "reviewed_at": "2026-07-26",
        "reviewer": "medication_depletion_section_03_content_audit",
        "citation_review_note": "Section 3 content audit: PMID 30896627 is a phenytoin-monotherapy meta-analysis reporting lower serum B12. Re-enabled only at this direct-drug scope.",
    },
    "DEP_ANTICONVULSANTS_VITAMINK": {
        "mechanism": "The pregnancy literature on enzyme-inducing antiseizure medications and vitamin K is mixed. A small older study found lower neonatal vitamin-K markers without antenatal supplementation, while a later review did not find evidence of increased neonatal hemorrhagic disease overall.",
        "clinical_impact": "Pregnancy-specific vitamin K decisions should be individualized with obstetric and neurology care; this is not evidence of a routine vitamin K deficiency in every person taking an antiseizure medication.",
        "recommendation": "If pregnant or planning pregnancy while taking an enzyme-inducing antiseizure medication, discuss vitamin K and newborn-bleeding considerations with the neurologist and obstetric clinician. Do not self-start high-dose vitamin K.",
        "evidence_level": "possible",
        "monitoring_note": "Antenatal vitamin K is an individualized obstetric decision, not a routine self-care recommendation.",
        "sources": [
            {"source_type": "pubmed", "label": "Does vitamin K prophylaxis prevent bleeding in neonates exposed to enzyme-inducing antiepileptic drugs in utero? Can Fam Physician. 2006.", "url": "https://pubmed.ncbi.nlm.nih.gov/16812962/"},
            {"source_type": "pubmed", "label": "Supplementation of vitamin K in pregnant women receiving anticonvulsant therapy prevents neonatal vitamin K deficiency. Am J Obstet Gynecol. 1993.", "url": "https://pubmed.ncbi.nlm.nih.gov/8456897/"},
        ],
        "alert_headline": "Discuss vitamin K only in pregnancy-specific care",
        "alert_body": "During long-term antiseizure treatment in pregnancy, vitamin K decisions need individualized obstetric and neurology guidance. Routine supplementation is not established.",
        "acknowledgement_note": "Pregnancy planning with an antiseizure medication is best coordinated with the prescribing and obstetric teams.",
        "monitoring_tip_short": "If pregnant or planning pregnancy, ask your care team about vitamin K guidance.",
        "citation_review_status": "verified",
        "reviewed_at": "2026-07-26",
        "reviewer": "medication_depletion_section_03_content_audit",
        "citation_review_note": "Section 3 content audit: replaced ghost PMID 14506311. PMID 8456897 reports neonatal biochemical markers in a small older study; PMID 16812962 concludes routine antenatal prophylaxis is not supported. Copy preserves that uncertainty.",
    },
    "DEP_ANTICONVULSANTS_BIOTIN": {
        "drug_ref": {"type": "class", "id": "class:anticonvulsants", "display_name": "Anticonvulsants / antiseizure medications (scope under review)"},
        "mechanism": "Long-term treatment with some anticonvulsants has been associated with increased biotin catabolism. Available studies include carbamazepine, phenytoin, and phenobarbital; they do not establish a valproate-specific effect.",
        "clinical_impact": "The available studies show mixed biotin-status indicators. This record is withheld while its drug-specific scope and consumer implications are reviewed.",
        "recommendation": "Do not use this inactive record to guide supplementation. Discuss symptoms or nutrition concerns with a clinician.",
        "evidence_level": "possible",
        "monitoring_note": "Suppressed pending a reviewed, drug-specific clinical claim.",
        "sources": [
            {"source_type": "pubmed", "label": "Biotin catabolism is accelerated in adults receiving long-term therapy with anticonvulsants. J Nutr. 1997.", "url": "https://pubmed.ncbi.nlm.nih.gov/9371938/"},
            {"source_type": "pubmed", "label": "Disturbances in biotin metabolism in children undergoing long-term anticonvulsant therapy. J Nutr. 1998.", "url": "https://pubmed.ncbi.nlm.nih.gov/9523856/"},
        ],
        "alert_body": "This long-term relationship is under review and is not shown to users.",
        "acknowledgement_note": "This relationship is under review and is not shown to users.",
        "monitoring_tip_short": "This relationship is under review and is not shown to users.",
        "citation_review_status": "needs_revision",
        "reviewed_at": "2026-07-26",
        "reviewer": "medication_depletion_section_03_content_audit",
        "citation_review_note": "Section 3 content audit: PMID 9371938 and PMID 9523856 support an anticonvulsant-class signal, but the measured child cohorts were carbamazepine/phenytoin/phenobarbital and neither study establishes valproate exposure. The valproate claim is therefore suppressed pending direct evidence and a new scope decision.",
    },
    "DEP_ANTICONVULSANTS_LCARNITINE": {
        "mechanism": "Long-term valproic acid treatment can reduce carnitine availability and impair fatty-acid oxidation. A pediatric study observed an altered fuel-use pattern that improved after carnitine supplementation.",
        "clinical_impact": "Carnitine depletion is a recognized concern in long-term valproate care, particularly in children and people with clinical risk factors. Acute valproate toxicity is a separate urgent clinical situation and is not represented by this routine monitoring record.",
        "recommendation": "Discuss symptoms, risk factors, and whether carnitine testing or supplementation is appropriate with the clinician managing valproate. Do not self-dose based on this record.",
        "evidence_level": "probable",
        "monitoring_note": "Testing and treatment decisions should be individualized, with particular attention to children and people with clinical symptoms or liver concerns.",
        "sources": [{"source_type": "pubmed", "label": "Carnitine-dependent changes of metabolic fuel consumption during long-term treatment with valproic acid. J Pediatr. 1994.", "url": "https://pubmed.ncbi.nlm.nih.gov/8040784/"}],
        "alert_body": "Long-term valproate use can be associated with lower carnitine availability, especially in children. A clinician can decide whether testing or treatment is appropriate.",
        "acknowledgement_note": "Carnitine questions can be discussed as part of long-term valproate care.",
        "monitoring_tip_short": "Ask whether carnitine assessment fits your treatment plan.",
        "citation_review_status": "verified",
        "reviewed_at": "2026-07-26",
        "reviewer": "medication_depletion_section_03_content_audit",
        "citation_review_note": "Section 3 content audit: PMID 8040784 is a long-term pediatric valproic-acid study. Copy removes routine dosing and separates chronic monitoring from acute toxicity care.",
    },
}

# Its own mechanism hedges ("may reduce", "may also increase"), evidence_level is
# "probable", and the source is an NLM catalog record rather than a study — not
# enough to ship a B12 claim.  Suppressed, not deleted: the signal is plausible
# and returns if a real citation is found.
# The inducer-class note recorded a deferral that Section 3 has now resolved.
STALE_NOTE_FRAGMENT = "its biotin/L-carnitine depletion records stay on class:anticonvulsants"
NEW_INDUCER_NOTE = (
    "Curated enzyme-inducer subset of class:anticonvulsants (carbamazepine, "
    "phenytoin, phenobarbital, primidone). Carries every induction-driven "
    "depletion: calcium and the pregnancy-specific vitamin K record. Direct "
    "carbamazepine and phenytoin citations are kept on their individual rxcuis. "
    "Valproate is excluded because it INHIBITS CYP450 and its L-carnitine record "
    "lives on class:valproate (Section 3, 2026-07-26). Oxcarbazepine remains "
    "excluded as a weaker, dose-dependent inducer pending separate review. All 4 "
    "rxcuis content-verified against RxNorm."
)


def _load(path: Path):
    return json.loads(path.read_text())


def _save(path: Path, blob) -> None:
    path.write_text(json.dumps(blob, indent=2, ensure_ascii=False) + "\n")


def apply(check_only: bool = False) -> int:
    classes_blob = _load(CLASSES_PATH)
    depl_blob = _load(DEPLETIONS_PATH)
    classes = classes_blob["classes"]
    by_id = {e["id"]: e for e in depl_blob["depletions"]}
    changes: list[str] = []

    # 1. class:valproate ----------------------------------------------------
    if classes.get(VALPROATE) != VALPROATE_CLASS:
        classes[VALPROATE] = VALPROATE_CLASS
        changes.append(f"+ {VALPROATE} ({len(VALPROATE_CLASS['member_rxcuis'])} members)")

    # 2. inducer-class note (records a deferral Section 3 resolved) ----------
    inducer = classes[INDUCERS]
    if inducer.get("notes") != NEW_INDUCER_NOTE:
        inducer["notes"] = NEW_INDUCER_NOTE
        changes.append(f"~ {INDUCERS}.notes refreshed")

    # 3. metadata ------------------------------------------------------------
    total = sum(len(c.get("member_rxcuis") or []) for c in classes.values())
    meta = classes_blob["_metadata"]
    # total_entries and total_classes are both the class count here — the
    # metadata contract reads total_entries, the schema test reads total_classes.
    wanted = {
        "total_classes": len(classes),
        "total_entries": len(classes),
        "total_members": total,
        "last_updated": "2026-07-26",
    }
    if any(meta.get(k) != v for k, v in wanted.items()):
        meta.update(wanted)
        changes.append(f"~ _metadata: {len(classes)} classes / {total} members")

    # 4. re-attributions, one record at a time -------------------------------
    for entry_id, class_id, display in REATTRIBUTIONS:
        ref = by_id[entry_id]["drug_ref"]
        if ref.get("id") != class_id or ref.get("display_name") != display:
            ref["type"] = "class"
            ref["id"] = class_id
            ref["display_name"] = display
            changes.append(f"~ {entry_id} -> {class_id}")

    # 5. prose that the new scope contradicts --------------------------------
    for entry_id, fields in TEXT_REWRITES.items():
        for field, text in fields.items():
            if by_id[entry_id].get(field) != text:
                by_id[entry_id][field] = text
                changes.append(f"~ {entry_id}.{field}")

    depletion_meta = depl_blob["_metadata"]
    if depletion_meta.get("last_updated") != "2026-07-26":
        depletion_meta["last_updated"] = "2026-07-26"
        changes.append("~ medication_depletions metadata last_updated")

    if not changes:
        print("Section 3: already applied (no changes).")
        return 0

    print("Section 3 changes:")
    for c in changes:
        print(f"  {c}")
    if check_only:
        print("\n--check: nothing written.")
        return 1

    _save(CLASSES_PATH, classes_blob)
    _save(DEPLETIONS_PATH, depl_blob)
    print(f"\nWrote {CLASSES_PATH.name} and {DEPLETIONS_PATH.name}.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report without writing")
    sys.exit(apply(check_only=ap.parse_args().check))
