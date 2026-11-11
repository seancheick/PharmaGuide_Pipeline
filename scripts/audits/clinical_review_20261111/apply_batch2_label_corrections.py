"""Batch 2 of Dr. Pham's 2026-11-11 review: four label-backed corrections.

Run once from the repo root:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch2_label_corrections.py

Decisions: DR_PHAM_REVIEW_20261111.md (A3, B1, B2, F9); rows mapped in DISPOSITIONS_20261111.md.
Every quoted label passage was read by the agent from DailyMed's v2 SPL service or the UK EMC SmPC on
2026-11-11; identifiers were checked live (RxNav, UMLS, GSRS, PubMed).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

CURATED = REPO / "scripts/data/curated_interactions/curated_interactions_v1.json"
MED_MED = REPO / "scripts/data/curated_interactions/med_med_pairs_v1.json"
RULES = REPO / "scripts/data/ingredient_interaction_rules.json"
IQM = REPO / "scripts/data/ingredient_quality_map.json"

REVIEW_FILE = "audits/clinical_review_20261111/DR_PHAM_REVIEW_20261111.md"
REVIEW_NOTE = f"Severity decided by Dr. Pham (clinical review 2026-11-11, {REVIEW_FILE}); label passages read by agent."


def label(setid: str) -> str:
    return f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"


PARNATE = label("b72d8187-dfcc-4ea0-b5e9-c0be95b69a27")
NCCIH_SAME = "https://www.nccih.nih.gov/health/sadenosyllmethionine-same-in-depth"
GEMFIBROZIL = label("cf32b795-bf42-4861-b273-06d27de3f21d")
ZOCOR = label("8f55d5de-5a4f-4a39-8c84-c53976dd6af9")
STATIN_LABELS = [
    ZOCOR,
    label("325a5d0e-9a72-4015-9fcd-1655fb504cee"),  # CRESTOR
    label("a60cc18b-0631-4cf0-b021-9f52224ece65"),  # LIPITOR
    label("42ccbca7-fa52-4df9-8f1a-ea7da7312883"),  # pravastatin
    label("df7ddf4f-d569-431e-81f1-9129d7043150"),  # lovastatin
    label("726ea2db-f1b0-4b73-a515-02157db88a42"),  # LESCOL XL
    label("44dcbf97-99ec-427c-ba50-207e0069d6d2"),  # LIVALO
]
CIPRO = label("888dc7f9-ad9c-4c00-8d50-8ddfd9bd27c0")
UK_ACETYLCYSTEINE = "https://www.medicines.org.uk/emc/product/2488/smpc"


def verification(note: str) -> dict:
    return {
        "status": "verified",
        "verified_at": "2026-11-11",
        "verified_with": {"rxnorm": True, "umls": True, "pubmed": True},
        "method": "agent_label_content_review_2026_11_11",
        "notes": f"{note} {REVIEW_NOTE}",
    }


MUSCLE = "Report unexplained muscle pain, tenderness or weakness promptly."


def same_pair(row: dict) -> None:
    row.update({
        "mechanism": (
            "SAMe raises serotonin activity. The tranylcypromine (PARNATE) label lists SAMe as contraindicated "
            "because combining it with the MAOI can cause serotonin syndrome. No study of SAMe with an MAOI was found."
        ),
        "source_urls": [PARNATE, NCCIH_SAME],
        "evidence_basis": "label_regulatory",
        "clinical_confidence": "medium",
        "evidence_notes": (
            "PARNATE (tranylcypromine) §4.1 and §7 list S-adenosyl-L-methionine (SAM-e) as contraindicated "
            "(serotonin syndrome). The labels for phenelzine (NARDIL), isocarboxazid (MARPLAN) and selegiline "
            "(EMSAM, ZELAPAR) do not name SAMe (read 2026-11-11); applying the contraindication to every MAOI is a "
            "documented class inference awaiting Dr. Pham's per-drug decision. NCCIH says SAMe might interact with "
            "serotonin-raising medicines."
        ),
        "verification": verification("PARNATE label read on DailyMed; other MAOI labels checked for SAMe."),
    })


def same_rule(rule: dict) -> None:
    sub = next(r for r in rule["drug_class_rules"] if r["drug_class_id"] == "maois")
    sub.update({
        "severity": "contraindicated",
        "mechanism": (
            "SAMe is a methyl donor studied as an antidepressant. The tranylcypromine (PARNATE) label lists SAMe as "
            "contraindicated because combining it with the MAOI can cause serotonin syndrome, and a toxic interaction "
            "with the antidepressant clomipramine has been reported. Other MAOI labels do not name SAMe, so applying "
            "this to every MAOI is a class inference. No study of SAMe with an MAOI was found."
        ),
        "action": (
            "If you take an MAOI, do not combine it with SAMe. Do not stop or change your MAOI to use SAMe; your "
            "prescriber manages any change and the washout time."
        ),
        "sources": [PARNATE, NCCIH_SAME, "https://pubmed.ncbi.nlm.nih.gov/7854515/",
                    "https://pubmed.ncbi.nlm.nih.gov/8434674/"],
        "alert_headline": "Do not combine with MAOIs",
        "alert_body": (
            "If you take an MAO inhibitor, do not combine it with this product. The tranylcypromine label lists SAMe "
            "as contraindicated because the combination can cause serotonin syndrome."
        ),
        "informational_note": "SAMe raises serotonin activity, which matters for anyone taking an MAOI or another antidepressant.",
        "clinical_review": {"reviewer": "Dr. Pham", "reviewed_at": "2026-11-11", "file": REVIEW_FILE},
    })
    rule["last_reviewed"] = "2026-11-11"
    rule["review_owner"] = "Dr. Pham (clinical review 2026-11-11, MAOI severity); label passages read by agent; pharmaguide_clinical_team"


def statin_class_pair(row: dict) -> None:
    row.update({
        "severity": "Major",
        "mechanism": (
            "Gemfibrozil raises blood levels of several statins and can cause muscle damage on its own. Together they "
            "increase the risk of myopathy and rhabdomyolysis; the gemfibrozil label says this muscle toxicity has led, "
            "in a high proportion of cases, to acute kidney failure and death."
        ),
        "management": (
            "Statin labels say to avoid gemfibrozil (the atorvastatin and pitavastatin labels say it is not "
            "recommended). For rosuvastatin, if the prescriber decides the combination cannot be avoided, the label "
            "limits the rosuvastatin dose. Do not stop or change either medicine yourself; ask your prescriber whether "
            f"this combination is right for you. {MUSCLE}"
        ),
        "source_urls": [GEMFIBROZIL, *STATIN_LABELS],
        "clinical_confidence": "high",
        "applies_to": "whole_class",
        "evidence_notes": (
            "Each marketed statin's own label, read 2026-11-11: simvastatin contraindicated (ZOCOR §4; also the "
            "gemfibrozil label); rosuvastatin avoid, and if unavoidable start at 5 mg and do not exceed 10 mg (CRESTOR); "
            "lovastatin avoid; fluvastatin avoid (LESCOL XL); pravastatin avoid; pitavastatin avoid / not recommended "
            "(LIVALO); atorvastatin not recommended (LIPITOR). Cerivastatin is withdrawn. Simvastatin has its own pair, "
            "DDI_SIMVASTATIN_GEMFIBROZIL, which replaces this class pair for simvastatin."
        ),
        "verification": verification("Gemfibrozil and seven statin labels read on DailyMed; dead FDA 2011 page removed."),
    })


SIMVASTATIN_PAIR = {
    "id": "DDI_SIMVASTATIN_GEMFIBROZIL",
    "type": "Med-Med",
    "agent1_name": "Simvastatin",
    "agent1_id": "36567",
    "agent2_name": "Gemfibrozil",
    "agent2_id": "4719",
    "severity": "Contraindicated",
    "interaction_effect_type": "Enhancer",
    "mechanism": (
        "Gemfibrozil raises simvastatin levels and can cause muscle damage on its own. The simvastatin and gemfibrozil "
        "labels both list the combination as contraindicated because of the risk of myopathy and rhabdomyolysis."
    ),
    "management": (
        "Simvastatin and gemfibrozil should not be used together. Do not stop or change either medicine yourself; "
        f"contact your prescriber, who will decide what to change. {MUSCLE}"
    ),
    "source_urls": [ZOCOR, GEMFIBROZIL],
    "verification": verification("ZOCOR §4 and the gemfibrozil Contraindications read on DailyMed."),
    "evidence_basis": "label_regulatory",
    "clinical_confidence": "high",
    "applies_to": "specific_drug",
    "agent1_canonical_id": None,
    "agent2_canonical_id": None,
    "direction": "harmful",
    "materiality": "presence",
}


def cipro_theophylline(row: dict) -> None:
    row.update({
        "severity": "Major",
        "mechanism": (
            "Ciprofloxacin blocks CYP1A2, the main enzyme that clears theophylline, so theophylline levels rise. The "
            "ciprofloxacin label reports serious and fatal reactions with the combination, including cardiac arrest, "
            "seizures and respiratory failure."
        ),
        "management": (
            "The ciprofloxacin label says to avoid this combination. If your prescriber decides it cannot be avoided, "
            "they will check your theophylline levels and adjust the dose. Do not change either medicine yourself. This "
            "warning is for ciprofloxacin tablets, liquid or IV; if you use ciprofloxacin only as eye or ear drops, ask "
            "your pharmacist whether it applies."
        ),
        "source_urls": [CIPRO],
        "clinical_confidence": "high",
        "applies_to": "specific_drug",
        "evidence_notes": (
            "CIPRO §5.10 (serious and fatal reactions) and §7 (Theophylline: Avoid Use; if unavoidable, monitor serum "
            "theophylline and adjust dosage) for systemic ciprofloxacin. The otic label has no interaction section. Saved "
            "medicines do not record route, so the pair applies to every ciprofloxacin entry and the text states the scope."
        ),
        "verification": verification("CIPRO §5.10 and §7 read on DailyMed."),
    })


NAC_PAIR = {
    "id": "DSI_NITROGLYCERIN_NAC",
    "type": "Med-Sup",
    "agent1_name": "Nitroglycerin",
    "agent1_id": "4917",
    "agent2_name": "N-Acetyl Cysteine (NAC)",
    "agent2_id": "C0001047",
    "severity": "Moderate",
    "interaction_effect_type": "Additive",
    "mechanism": (
        "NAC (acetylcysteine) can add to the blood-vessel-widening effect of nitroglycerin. An acetylcysteine product "
        "label says using them together causes significant low blood pressure, which can be severe, and headache. In a "
        "trial of oral NAC with nitroglycerin patches, side effects (mainly intolerable headache) were almost twice as "
        "common as with nitroglycerin alone."
    ),
    "management": (
        "If you use nitroglycerin, talk to your prescriber before taking NAC. If you use both, ask your prescriber how "
        "your blood pressure should be checked, and watch for dizziness, light-headedness, fainting or a severe "
        "headache; get medical help if they happen."
    ),
    "source_urls": [UK_ACETYLCYSTEINE, "https://pubmed.ncbi.nlm.nih.gov/9120179/"],
    "source_pmids": ["9120179"],
    "verification": verification("UK SmPC §4.5 read on EMC; PMID 9120179 abstract read; C0001047 (UMLS) and RxCUI 4917 checked live."),
    "evidence_basis": "label_regulatory",
    "clinical_confidence": "medium",
    "applies_to": "specific_drug",
    "evidence_notes": (
        "UK SmPC, Acetylcysteine 200 mg Powder for Oral Solution, §4.5 (read 2026-11-11): concurrent use causes "
        "significant hypotension and headache; monitor and warn for hypotension. US acetylcysteine labels (Acetadote, "
        "inhalation solution) do not mention nitroglycerin. PMID 9120179 (n=200, transdermal nitroglycerin with oral "
        "NAC) reports headache, not blood pressure. No source was read for other nitrates, so the pair names "
        "nitroglycerin only. No dose boundary is established."
    ),
    "agent1_canonical_id": None,
    "agent2_canonical_id": "nac",
    "direction": "harmful",
    "materiality": "presence",
}


def edit(path: Path, fn) -> None:
    blob = data_batch.load(path)
    fn(blob)
    data_batch.save(path, blob)


def curated(blob: dict) -> None:
    rows = {r["id"]: r for r in blob["interactions"]}
    same_pair(rows["DSI_MAOI_SAME"])
    assert "DSI_NITROGLYCERIN_NAC" not in rows
    blob["interactions"].append(NAC_PAIR)


def med_med(blob: dict) -> None:
    rows = {r["id"]: r for r in blob["interactions"]}
    statin_class_pair(rows["DDI_STATIN_GEMFIBROZIL"])
    cipro_theophylline(rows["DDI_THEOPHYLLINE_CIPRO"])
    assert "DDI_SIMVASTATIN_GEMFIBROZIL" not in rows
    blob["interactions"].append(SIMVASTATIN_PAIR)


def rules(blob: dict) -> None:
    same_rule(next(r for r in blob["interaction_rules"] if r["id"] == "RULE_IQM_SAME"))


def iqm(blob: dict) -> None:
    # verify_interactions.py maps a supplement CUI to its canonical id through this map, so the NAC pair keeps
    # canonical "nac" only if NAC's entry carries the CUI. C3181855 (a peptide) was rightly removed in October;
    # the exact concept was never restored.
    nac = blob["nac"]
    assert nac["cui"] is None and nac["rxcui"] == "197" and nac["external_ids"]["unii"] == "WYQ7N0BPYC"
    nac["cui"] = "C0001047"
    nac["cui_status"] = "verified"
    nac["cui_note"] = (
        "C0001047 = acetylcysteine (UMLS-verified 2026-11-11): atoms include RXNORM 197 (this entry's RxCUI), "
        "MSH D000111 N-Acetyl-L-cysteine and NCI C200 N-Acetyl Cysteine; UNII WYQ7N0BPYC is Acetylcysteine in GSRS. "
        "C3181855 (N-acetyl cysteine proline cysteine amide) was a different peptide."
    )


if __name__ == "__main__":
    edit(CURATED, curated)
    edit(MED_MED, med_med)
    edit(RULES, rules)
    edit(IQM, iqm)
