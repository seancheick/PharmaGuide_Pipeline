"""Batch 3c part 1: drug-specific fluoroquinolone spacing (rows A12 and A13).

Run once from the repo root:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch3c_fluoroquinolone_spacing.py

Decisions (Dr. Pham, DR_PHAM_REVIEW_20261111.md, A12/A13): zinc + fluoroquinolones is caution with each antibiotic's
own label interval, not injected forms; calcium + ciprofloxacin is caution with the label spacing, and calcium
supplements differ from dairy or fortified juice taken with a meal. Label passages read by an agent on 2026-11-11
(DailyMed SPL XML):
- CIPRO, setid 888dc7f9 (effective 2026-03-02), section 2.4 and 7: at least 2 hours before or 6 hours after products
  containing calcium, iron or zinc; not with dairy products or calcium-fortified juices alone, but may be taken with a
  meal that contains these products. Generic ciprofloxacin tablets, setid d10f7c93, say the same.
- Levofloxacin tablets (Chartwell RX), setid 5c6c117c (effective 2026-06-29), section 2 and 7.1: at least two hours
  before or two hours after multivitamin preparations with zinc.
- Moxifloxacin tablets, setid 1e6bc886 (effective 2025-10-09), section 2.2 and 7.1: at least 4 hours before or 8 hours
  after products containing magnesium, aluminum, iron or zinc, including multivitamins.
RxCUIs 2551, 82122 and 139462 checked live on RxNav (ingredient names match). The other class members (ofloxacin,
delafloxacin, gemifloxacin) keep the class pair, which tells users to follow their own label.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

CURATED = REPO / "scripts/data/curated_interactions/curated_interactions_v1.json"
REVIEW_NOTE = (
    "Severity and spacing decided by Dr. Pham (clinical review 2026-11-11, DR_PHAM_REVIEW_20261111.md A12/A13); "
    "label passages read by agent."
)
REVIEW_PMID = "1524699"  # Drug Saf 1992, "Drug interactions with quinolone antibacterials" (review)


def label(setid: str) -> str:
    return f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"


CIPRO_LABEL = label("888dc7f9-ad9c-4c00-8d50-8ddfd9bd27c0")
CIPRO_GENERIC = label("d10f7c93-a08b-4e9c-bfa2-6646e3ea21bd")
LEVO_LABEL = label("5c6c117c-9d91-48f4-9aaa-ee70b99218c2")
MOXI_LABEL = "https://dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=1e6bc886-eec9-4cd8-be78-7563817457f2&type=display"


def verification(note: str) -> dict:
    return {
        "status": "verified",
        "verified_at": "2026-11-11",
        "verified_with": {"rxnorm": True, "umls": True, "pubmed": True},
        "method": "agent_label_content_review_2026_11_11",
        "notes": f"{note} {REVIEW_NOTE}",
    }


def zinc_pair(pair_id: str, name: str, rxcui: str, form: str, interval: str, url: str, passage: str) -> dict:
    return {
        "id": pair_id,
        "type": "Med-Sup",
        "agent1_name": name.capitalize(),
        "agent1_id": rxcui,
        "agent2_name": "Zinc",
        "agent2_id": "C0043481",
        "severity": "Moderate",
        "interaction_effect_type": "Inhibitor",
        "mechanism": (
            f"Zinc can bind {name} in the gut and reduce how much of the antibiotic is absorbed, which can make the "
            "infection treatment less effective."
        ),
        "management": (
            f"Take {name} {form} {interval} zinc supplements or multivitamins that contain zinc, as the {name} label "
            f"directs. This applies to {name} taken by mouth; injected {name} is not affected."
        ),
        "source_urls": [url, f"https://pubmed.ncbi.nlm.nih.gov/{REVIEW_PMID}/"],
        "source_pmids": [REVIEW_PMID],
        "verification": verification(f"{passage} RxCUI {rxcui} and C0043481 checked live."),
        "evidence_basis": "label_regulatory",
        "clinical_confidence": "high",
        "applies_to": "specific_drug",
        "evidence_notes": passage,
        "agent1_canonical_id": None,
        "agent2_canonical_id": "zinc",
        "direction": "harmful",
        "materiality": "presence",
    }


NEW_PAIRS = [
    zinc_pair(
        "DSI_ZINC_CIPROFLOXACIN", "ciprofloxacin", "2551", "tablets or liquid",
        "at least 2 hours before or 6 hours after", CIPRO_LABEL,
        "CIPRO label (setid 888dc7f9, effective 2026-03-02) sections 2.4 and 7: take at least 2 hours before or 6 hours "
        "after products containing calcium, iron or zinc.",
    ),
    zinc_pair(
        "DSI_ZINC_LEVOFLOXACIN", "levofloxacin", "82122", "tablets or liquid",
        "at least 2 hours before or 2 hours after", LEVO_LABEL,
        "Levofloxacin tablets label (setid 5c6c117c, effective 2026-06-29) sections 2 and 7.1: at least two hours "
        "before or two hours after multivitamin preparations with zinc.",
    ),
    zinc_pair(
        "DSI_ZINC_MOXIFLOXACIN", "moxifloxacin", "139462", "tablets",
        "at least 4 hours before or 8 hours after", MOXI_LABEL,
        "Moxifloxacin tablets label (setid 1e6bc886, effective 2025-10-09) sections 2.2 and 7.1: at least 4 hours "
        "before or 8 hours after products containing magnesium, aluminum, iron or zinc, including multivitamins.",
    ),
]


def curated(blob: dict) -> None:
    rows = {r["id"]: r for r in blob["interactions"]}
    for pair in NEW_PAIRS:
        assert pair["id"] not in rows, pair["id"]

    zinc = rows["DSI_ZINC_FLUOROQUINOLONE"]
    assert zinc["severity"] == "Major" and "differs by drug" in zinc["management"]
    zinc["severity"] = "Moderate"
    zinc["management"] = (
        "Separate oral fluoroquinolones from zinc-containing supplements and multivitamins. The timing interval "
        "differs by drug, so follow the prescription label or pharmacist instructions; do not apply one interval to "
        "the entire class. Injected forms are not affected."
    )
    zinc["verification"] = verification(
        "Class pair kept for fluoroquinolones without an exact pair (ofloxacin, delafloxacin, gemifloxacin); "
        "ciprofloxacin, levofloxacin and moxifloxacin have exact pairs with their label intervals."
    )

    calcium = rows["DSI_CALCIUM_CIPROFLOXACIN"]
    assert calcium["severity"] == "Major" and "2 hours before or 6 hours after" in calcium["management"]
    calcium["severity"] = "Moderate"
    calcium["management"] = (
        "Take ciprofloxacin tablets or liquid at least 2 hours before or 6 hours after calcium supplements, "
        "multivitamins with calcium, or calcium-containing antacids, as the ciprofloxacin label directs. Do not take "
        "ciprofloxacin with milk, yogurt or calcium-fortified juice on their own; the label allows taking it with a "
        "meal that contains these foods. This applies to ciprofloxacin taken by mouth; injected ciprofloxacin is not "
        "affected."
    )
    calcium["source_urls"] = [CIPRO_LABEL, CIPRO_GENERIC, f"https://pubmed.ncbi.nlm.nih.gov/{REVIEW_PMID}/"]
    calcium["verification"] = verification(
        "CIPRO label (setid 888dc7f9, effective 2026-03-02) sections 2.4 and 7: at least 2 hours before or 6 hours "
        "after calcium-containing products; not with dairy products or calcium-fortified juices alone, but may be "
        "taken with a meal that contains these products. RxCUI 2551 checked live."
    )

    blob["interactions"].extend(NEW_PAIRS)


if __name__ == "__main__":
    blob = data_batch.load(CURATED)
    curated(blob)
    data_batch.save(CURATED, blob)
