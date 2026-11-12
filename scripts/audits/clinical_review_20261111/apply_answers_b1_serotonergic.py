"""Batch 1 of Dr. Pham's signed answers (2026-11-12): serotonergic harmonization.

Run once from the repo root:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_answers_b1_serotonergic.py

Authority: DR_PHAM_ANSWERS_20261112.md Part A (Q1; section 2, "St. John's wort with SSRIs/SNRIs" and "5-HTP with
serotonergic medicines"), and Part B 3D (Sean's finding, label-sourced: rasagiline and safinamide).

- SAMe + MAOIs (Q1). Class pair DSI_MAOI_SAME Contraindicated -> Major, so it matches the class profile rule
  RULE_IQM_SAME/maois (avoid): one answer for an MAOI that is not identified further. Exact pairs carry the
  contraindications: DSI_TRANYLCYPROMINE_SAME (PARNATE names SAM-e; unchanged) and new DSI_PHENELZINE_SAME (NARDIL
  contraindicates serotoninergic agents as a category; applying it to SAMe is the clinical interpretation Dr. Pham
  signed). Confirmed EMSAM is contraindicated through its serotonergic-drug language (section 7.1), but medicines
  are matched by RxNorm ingredient, so EMSAM and oral selegiline cannot be told apart here: both receive avoid.
  Consumer action is Q1's text.
- 5-HTP + SSRIs/SNRIs (section 2). DSI_SSRI_5HTP Major -> Contraindicated, matching the profile rule; Health
  Canada's 5-HTP monograph (Contraindication(s), all uses: antidepressants) is the source, with its jurisdiction
  recorded. The pair's medicine side widens from SSRIs to SSRIs and SNRIs, the profile rule's audience (the
  monograph names antidepressants). Self-managed washout instructions leave the 5-HTP records.
- St. John's wort + SSRIs/SNRIs (section 2). Avoid on both records (pair Contraindicated -> Major; rule
  contraindicated -> avoid). Every SSRI/SNRI label read (ZOLOFT, EFFEXOR XR, PRISTIQ, FETZIMA, SAVELLA) lists
  St. John's wort among serotonergic drugs that raise serotonin-syndrome risk, with monitoring as the management;
  none contraindicates it. The pair widens to SSRIs and SNRIs like the rule. No washout interval. The FDA
  citalopram QT communication leaves the pair's sources (it does not concern St. John's wort).
- Rasagiline and safinamide (Part B 3D). Exact pairs DSI_RASAGILINE_SJW and DSI_SAFINAMIDE_SJW, Contraindicated
  from each label's section 4. Neither medicine joins the MAOI class: its other rules were not reviewed for them.
  Agent review under the 2026-11-06 delegation (label-sourced identity and scope), not a clinician review.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

CURATED = REPO / "scripts/data/curated_interactions/curated_interactions_v1.json"
RULES = REPO / "scripts/data/ingredient_interaction_rules.json"

ANSWERS = "audits/clinical_review_20261111/DR_PHAM_ANSWERS_20261112.md"
TODAY = "2026-11-12"
DM = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid="
PARNATE = DM + "b72d8187-dfcc-4ea0-b5e9-c0be95b69a27"
NARDIL = DM + "513a41d0-37d4-4355-8a6d-a2c643bce6fa"
EMSAM = DM + "b891bd9f-fdb8-4862-89c5-ecdd700398a3"
ZOLOFT = DM + "fda754f6-d0f3-4dce-a17a-927d64f912f7"
EFFEXOR_XR = DM + "c848a5d8-ba94-4c84-80e3-0bf35fb8e32e"
RASAGILINE = DM + "68cef20f-10c0-475e-af95-b7799355c7e9"
XADAGO = DM + "c4d65f28-983f-42b4-bb23-023ae0fe81b2"
NCCIH_SAME = "https://www.nccih.nih.gov/health/sadenosyllmethionine-same-in-depth"
NCCIH_SJW = "https://www.nccih.nih.gov/health/st-johns-wort"
HC_5HTP = "https://webprod.hc-sc.gc.ca/nhpid-bdipsn/atReq?atid=5htp&lang=eng"
MSKCC_5HTP = "https://www.mskcc.org/cancer-care/integrative-medicine/herbs/5-htp-01"
FDA_CITALOPRAM_QT = (
    "https://www.fda.gov/drugs/drug-safety-and-availability/"
    "fda-drug-safety-communication-revised-recommendations-celexa-citalopram"
)
SSRI_SNRI = ("class:antidepressants_ssri_snri", "SSRIs and SNRIs (class)")

SAME_ACTION = (
    "Do not add SAMe while taking an MAOI without your prescriber's approval. Do not stop or switch your prescribed "
    "medicine to use SAMe."
)
SJW_SSRI_ACTION = (
    "Avoid St. John's wort while taking an SSRI or SNRI unless your prescriber directs and monitors the combination. "
    "Do not stop or switch your antidepressant on your own. Seek emergency care right away if signs of serotonin "
    "syndrome appear."
)
FIVE_HTP_SSRI_ACTION = (
    "Do not take 5-HTP with an SSRI or SNRI antidepressant. Do not stop or switch your antidepressant to use 5-HTP; "
    "your prescriber plans any change and the washout time. Seek emergency care for suspected serotonin syndrome."
)
SSRI_SNRI_LABELS_READ = (
    "SSRI and SNRI labels read on DailyMed 2026-11-12 (ZOLOFT fda754f6, EFFEXOR XR c848a5d8, PRISTIQ 0f43610c, "
    "FETZIMA f371258d, SAVELLA 16a4a314) list St. John's wort among serotonergic drugs that raise serotonin-syndrome "
    "risk; their management is monitoring and none contraindicates the combination."
)


def verification(note: str, rxnorm: bool = True, pubmed: bool = False) -> dict:
    return {
        "status": "verified",
        "verified_at": TODAY,
        "verified_with": {"rxnorm": rxnorm, "umls": True, "pubmed": pubmed},
        "method": "agent_label_content_review_2026_11_12",
        "notes": note,
    }


def review(notes: str) -> dict:
    return {"reviewer": "Dr. Pham", "reviewed_at": TODAY, "file": ANSWERS, "notes": notes}


# --- curated pairs -------------------------------------------------------------------------------------------------

def maoi_same(row: dict) -> None:
    assert row["severity"] == "Contraindicated" and row["agent1_id"] == "class:maois"
    row.update({
        "severity": "Major",
        "mechanism": (
            "SAMe raises serotonin activity, and an MAOI taken with a serotonergic product can cause serotonin "
            "syndrome. The tranylcypromine (PARNATE) label lists SAM-e as contraindicated. The phenelzine (NARDIL) "
            "and selegiline patch (EMSAM) labels contraindicate serotonergic drugs as a category without naming SAMe. "
            "Other MAOI labels do not name SAMe, so for them this warning is a class inference. No study of SAMe with "
            "an MAOI was found."
        ),
        "management": f"{SAME_ACTION} Your prescriber manages any medication change and the washout time.",
        "source_urls": [PARNATE, NARDIL, EMSAM, NCCIH_SAME],
        "evidence_notes": (
            "Class record (avoid; prescriber review required). Dr. Pham, 2026-11-12 (Q1): tranylcypromine is "
            "contraindicated (exact pair DSI_TRANYLCYPROMINE_SAME); phenelzine is contraindicated through NARDIL's "
            "serotonergic-agent category, a clinical interpretation (exact pair DSI_PHENELZINE_SAME); confirmed EMSAM "
            "is contraindicated through its serotonergic-drug language (section 7.1), but medicines are matched by "
            "RxNorm ingredient, so an EMSAM user cannot be told apart from oral selegiline and receives this record; "
            "oral selegiline (ZELAPAR) and other or unidentified MAOIs are avoid, a documented class inference. The "
            "EMSAM 6 mg exception concerns dietary tyramine only."
        ),
        "verification": verification(
            f"PARNATE, NARDIL and EMSAM labels read on DailyMed 2026-11-12. Severity: Dr. Pham, {ANSWERS} (Q1)."
        ),
    })


def phenelzine_same(class_row: dict) -> dict:
    return {
        "id": "DSI_PHENELZINE_SAME",
        "type": "Med-Sup",
        "agent1_name": "Phenelzine",
        "agent1_id": "8123",
        "agent2_name": class_row["agent2_name"],
        "agent2_id": class_row["agent2_id"],
        "severity": "Contraindicated",
        "interaction_effect_type": "Additive",
        "mechanism": (
            "SAMe raises serotonin activity. The phenelzine (NARDIL) label says phenelzine must not be used with "
            "serotonergic agents because of serious, sometimes fatal reactions. The label does not name SAMe; treating "
            "SAMe as one of those agents is a clinical interpretation."
        ),
        "management": (
            "Do not take SAMe with phenelzine. Do not stop or switch phenelzine to use SAMe; your prescriber manages "
            "any medication change and the washout time."
        ),
        "source_urls": [NARDIL, NCCIH_SAME],
        "source_pmids": [],
        "verification": verification(
            "NARDIL label (DailyMed setid 513a41d0, effective 2026-11-05) read 2026-11-12: Contraindications and "
            "Precautions (Drug Interactions) prohibit concomitant serotoninergic agents; SAMe is not named. RxCUI 8123 "
            f"(phenelzine, IN, active) checked on RxNav. Severity: Dr. Pham, {ANSWERS} (Q1)."
        ),
        "evidence_basis": "label_regulatory",
        "clinical_confidence": "low",
        "applies_to": "specific_drug",
        "evidence_notes": (
            "NARDIL (phenelzine) contraindicates concomitant serotoninergic agents as a category. SAMe is not named; "
            "applying the category to SAMe is the clinical interpretation Dr. Pham signed on 2026-11-12 (Q1), recorded "
            "separately from an explicitly named contraindication such as PARNATE's (DSI_TRANYLCYPROMINE_SAME)."
        ),
        "agent1_canonical_id": None,
        "agent2_canonical_id": class_row["agent2_canonical_id"],
        "direction": "harmful",
        "materiality": "presence",
    }


def ssri_5htp(row: dict) -> None:
    assert row["severity"] == "Major" and row["agent1_id"] == "class:ssris"
    row.update({
        "agent1_id": SSRI_SNRI[0],
        "agent1_name": SSRI_SNRI[1],
        "severity": "Contraindicated",
        "mechanism": (
            "5-HTP is a serotonin precursor. Taken with an SSRI or SNRI antidepressant it adds to serotonin activity "
            "and can contribute to serotonin syndrome. Health Canada's 5-HTP monograph lists use with antidepressants "
            "as a contraindication. A reported sertraline case involved several medicines and supplements; it supports "
            "a serious concern but no event rate or safe dose."
        ),
        "management": (
            "Do not take 5-HTP with an SSRI or SNRI antidepressant. Do not stop or switch your antidepressant to use "
            "5-HTP; your prescriber plans any change and the washout time. Seek emergency care for suspected "
            "serotonin syndrome, such as agitation with fever, muscle rigidity or confusion."
        ),
        "source_urls": [HC_5HTP, MSKCC_5HTP, "https://pubmed.ncbi.nlm.nih.gov/28839121/"],
        "source_pmids": ["28839121"],
        "evidence_basis": "label_regulatory",
        "clinical_confidence": "medium",
        "evidence_notes": (
            "Health Canada natural health product monograph '5-Hydroxy-L-tryptophan' (dated 2024-08-28), Risk "
            "information, Contraindication(s), all uses: do not use if you are taking antidepressants. Jurisdiction: "
            "Canada; scope: licensed natural health products with 5-HTP. Severity: Dr. Pham, 2026-11-12 (section 2). "
            "The medicine side covers SSRIs and SNRIs, the profile rule's audience; the monograph names "
            "antidepressants. MSKCC advises against unsupervised use with serotonergic medicines; PMID 28839121 is a "
            "sertraline case with several co-exposures."
        ),
        "verification": verification(
            f"Health Canada 5-HTP monograph read 2026-11-12. Severity: Dr. Pham, {ANSWERS} (section 2).", pubmed=True
        ),
    })


def maoi_5htp(row: dict) -> None:
    assert row["severity"] == "Contraindicated" and row["agent1_id"] == "class:maois"
    row.update({
        "source_urls": [*row["source_urls"], HC_5HTP, PARNATE],
        "evidence_notes": (
            "Health Canada's 5-HTP monograph (Canada, dated 2024-08-28) contraindicates use with antidepressants; the "
            "tranylcypromine (PARNATE) label lists hydroxytryptophan among products not to combine with it. MSKCC "
            "reports mania with an MAOI and 5-HTP and serotonin syndrome with linezolid. Severity kept as strong "
            "protection (Dr. Pham, 2026-11-12, section 2)."
        ),
        "verification": verification(
            f"Health Canada monograph and PARNATE section 4 read 2026-11-12. Dr. Pham, {ANSWERS} (section 2)."
        ),
    })


def ssri_sjw(row: dict) -> None:
    assert row["severity"] == "Contraindicated" and row["agent1_id"] == "class:ssris"
    sources = [u for u in row["source_urls"] if u != FDA_CITALOPRAM_QT and "ataglance" not in u]
    row.update({
        "agent1_id": SSRI_SNRI[0],
        "agent1_name": SSRI_SNRI[1],
        "severity": "Major",
        "mechanism": (
            "St. John's wort has serotonergic activity. Combining it with an SSRI or SNRI can cause serotonin "
            "syndrome, which can be life-threatening; SSRI and SNRI labels list it among serotonergic products that "
            "raise that risk. Symptoms can include agitation, high temperature, muscle rigidity or clonus, and "
            "seizures."
        ),
        "management": SJW_SSRI_ACTION,
        "source_urls": [ZOLOFT, EFFEXOR_XR, *sources],
        "evidence_notes": (
            f"{SSRI_SNRI_LABELS_READ} Avoid is Dr. Pham's decision (2026-11-12, section 2); contraindicated is "
            "reserved for an exact source, and none was found. No universal washout is given. The medicine side "
            "covers SSRIs and SNRIs, the profile rule's audience."
        ),
        "verification": verification(
            f"{SSRI_SNRI_LABELS_READ} Severity: Dr. Pham, {ANSWERS} (section 2).", pubmed=True
        ),
    })
    assert FDA_CITALOPRAM_QT not in row["source_urls"]


def mao_b_sjw(pair_id: str, name: str, rxcui: str, label: str, mechanism: str, note: str, sjw: dict) -> dict:
    return {
        "id": pair_id,
        "type": "Med-Sup",
        "agent1_name": name,
        "agent1_id": rxcui,
        "agent2_name": sjw["agent2_name"],
        "agent2_id": sjw["agent2_id"],
        "severity": "Contraindicated",
        "interaction_effect_type": "Additive",
        "mechanism": mechanism,
        "management": (
            f"Do not take St. John's wort with {name.lower()}. Do not stop or change {name.lower()} yourself; ask your "
            "prescriber about any change. Seek emergency care for signs of serotonin syndrome."
        ),
        "source_urls": [label],
        "source_pmids": [],
        "verification": verification(
            f"{note} Agent review under the 2026-11-06 delegation (label-sourced identity and scope), not a "
            "clinician review; Part B 3D of the 2026-11-12 answers."
        ),
        "evidence_basis": "label_regulatory",
        "clinical_confidence": "medium",
        "applies_to": "specific_drug",
        "evidence_notes": (
            f"{note} Exact coverage only: {name.lower()} is not added to the MAOI class, whose other rules were not "
            "reviewed for it."
        ),
        "agent1_canonical_id": None,
        "agent2_canonical_id": sjw["agent2_canonical_id"],
        "direction": "harmful",
        "materiality": "presence",
    }


def curated(blob: dict) -> None:
    rows = blob["interactions"]
    by_id = {r["id"]: r for r in rows}
    assert not {"DSI_PHENELZINE_SAME", "DSI_RASAGILINE_SJW", "DSI_SAFINAMIDE_SJW"} & set(by_id)
    maoi_same(by_id["DSI_MAOI_SAME"])
    ssri_5htp(by_id["DSI_SSRI_5HTP"])
    maoi_5htp(by_id["DSI_MAOI_5HTP"])
    ssri_sjw(by_id["DSI_SSRI_SJW"])
    i = next(n for n, r in enumerate(rows) if r["id"] == "DSI_TRANYLCYPROMINE_SAME")
    rows.insert(i + 1, phenelzine_same(by_id["DSI_MAOI_SAME"]))
    sjw = by_id["DSI_MAOI_SJW"]
    j = next(n for n, r in enumerate(rows) if r["id"] == "DSI_MAOI_SJW")
    rows[j + 1:j + 1] = [
        mao_b_sjw(
            "DSI_RASAGILINE_SJW", "Rasagiline", "134748", RASAGILINE,
            "Rasagiline is an MAO-B inhibitor used for Parkinson's disease. Its label lists St. John's wort as "
            "contraindicated, next to medicines it contraindicates because of the risk of serotonin syndrome.",
            "Rasagiline tablets label (DailyMed setid 68cef20f, effective 2026-10-23), section 4: contraindicated for "
            "use with St. John's wort. RxCUI 134748 (rasagiline, IN, active) checked on RxNav 2026-11-12.",
            sjw,
        ),
        mao_b_sjw(
            "DSI_SAFINAMIDE_SJW", "Safinamide", "1922448", XADAGO,
            "Safinamide (Xadago) is an MAO-B inhibitor used for Parkinson's disease. Its label contraindicates St. "
            "John's wort because the combination could cause life-threatening serotonin syndrome.",
            "XADAGO label (DailyMed setid c4d65f28, effective 2026-10-05), sections 4 and 7.3: concomitant use with "
            "St. John's wort is contraindicated. RxCUI 1922448 (safinamide, IN, active) checked on RxNav 2026-11-12.",
            sjw,
        ),
    ]


# --- profile rules -------------------------------------------------------------------------------------------------

def same_rule(sub: dict) -> None:
    assert sub["severity"] == "avoid" and sub["sources"][:2] == [PARNATE, NARDIL]
    sub.update({
        "mechanism": (
            "SAMe is a methyl donor studied as an antidepressant and raises serotonin activity. The tranylcypromine "
            "(PARNATE) label lists SAMe as contraindicated because of serotonin syndrome, and a toxic interaction with "
            "the antidepressant clomipramine has been reported. The phenelzine (NARDIL) and EMSAM patch labels "
            "contraindicate serotonergic drugs without naming SAMe; for other MAOIs this is a class inference. No "
            "study of SAMe with an MAOI was found."
        ),
        "action": (
            f"{SAME_ACTION} With tranylcypromine (Parnate), phenelzine (Nardil) or the Emsam patch, the combination "
            "is contraindicated."
        ),
        "alert_body": (
            "If you take an MAO inhibitor, avoid this product unless your prescriber approves. SAMe raises serotonin "
            "activity, and with some MAOIs the combination is contraindicated."
        ),
        "sources": [PARNATE, NARDIL, EMSAM, *sub["sources"][2:]],
        "clinical_review": review(
            "Q1: avoid as the class fallback, prescriber review required. The exact contraindications are the pairs "
            "DSI_TRANYLCYPROMINE_SAME (the label names SAM-e) and DSI_PHENELZINE_SAME (the label's serotonergic "
            "category, recorded as interpretation). Confirmed EMSAM is contraindicated through its serotonergic-drug "
            "language, but medicines are matched by ingredient, so EMSAM cannot be told apart from oral selegiline, "
            "which is avoid."
        ),
    })


def sjw_ssri_rule(sub: dict) -> None:
    assert sub["severity"] == "contraindicated"
    sub.update({
        "severity": "avoid",
        "mechanism": (
            "St. John's wort raises serotonin activity. SSRI and SNRI labels list it among serotonergic products that "
            "raise the risk of serotonin syndrome, a potentially life-threatening reaction (high temperature, clonus, "
            "agitation, seizures)."
        ),
        "action": SJW_SSRI_ACTION,
        "sources": [ZOLOFT, EFFEXOR_XR, NCCIH_SJW],
        "alert_headline": "Avoid combining with SSRIs or SNRIs",
        "alert_body": (
            "If you take an SSRI or SNRI antidepressant, avoid St. John's wort unless your prescriber approves. The "
            "combination can cause serotonin syndrome."
        ),
        "clinical_review": review(
            "Section 2: avoid unsupervised combination as the general action; contraindicated only with an exact "
            "source, and none of the SSRI/SNRI labels read contraindicates it. No universal washout. Pair "
            "DSI_SSRI_SJW changed with this record."
        ),
    })


def five_htp_ssri_rule(sub: dict) -> None:
    assert sub["severity"] == "contraindicated"
    sub.update({
        "mechanism": (
            "5-HTP is a serotonin precursor; SSRIs and SNRIs block serotonin reuptake. Together they can raise "
            "serotonin activity enough to contribute to serotonin syndrome (high temperature, clonus, agitation). "
            "Health Canada's 5-HTP monograph lists use with antidepressants as a contraindication."
        ),
        "action": FIVE_HTP_SSRI_ACTION,
        "sources": [HC_5HTP, *sub["sources"]],
        "clinical_review": review(
            "Section 2: do not combine, from the Health Canada 5-HTP monograph (jurisdiction Canada; contraindication "
            "with antidepressants). Pair DSI_SSRI_5HTP now carries the same severity and source."
        ),
    })


def five_htp_maoi_rule(sub: dict) -> None:
    assert sub["action"].endswith("Allow appropriate washout between MAOI discontinuation and 5-HTP use.")
    sub["action"] = (
        "Do not combine 5-HTP with MAOIs. Do not stop or switch your MAOI to use 5-HTP; your prescriber plans any "
        "change and the washout time."
    )
    sub["clinical_review"] = review(
        "Section 2: keep strong protection and harmonize the 5-HTP records; the self-managed washout instruction is "
        "removed."
    )


def rules(blob: dict) -> None:
    by_id = {r["id"]: r for r in blob["interaction_rules"]}

    def sub(rule_id: str, drug_class: str) -> dict:
        [row] = [s for s in by_id[rule_id]["drug_class_rules"] if s["drug_class_id"] == drug_class]
        return row

    same_rule(sub("RULE_IQM_SAME", "maois"))
    sjw_ssri_rule(sub("RULE_INGREDIENT_ST_JOHNS_WORT", "antidepressants_ssri_snri"))
    five_htp_ssri_rule(sub("RULE_IQM_5HTP_SEROTONIN", "antidepressants_ssri_snri"))
    five_htp_maoi_rule(sub("RULE_IQM_5HTP_SEROTONIN", "maois"))
    by_id["RULE_IQM_SAME"]["review_owner"] = (
        "Dr. Pham (MAOI severity: review 2026-11-11, signed answers 2026-11-12); label passages read by agent"
    )
    for rule_id in ("RULE_IQM_SAME", "RULE_INGREDIENT_ST_JOHNS_WORT", "RULE_IQM_5HTP_SEROTONIN"):
        by_id[rule_id]["last_reviewed"] = TODAY


def edit(path: Path, fn) -> None:
    blob = data_batch.load(path)
    fn(blob)
    data_batch.save(path, blob)


if __name__ == "__main__":
    edit(CURATED, curated)
    edit(RULES, rules)
