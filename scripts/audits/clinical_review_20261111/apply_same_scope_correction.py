"""SAMe + MAOI scope correction to batch 2 (PR #444) of Dr. Pham's 2026-11-11 review.

Run once from the repo root:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_same_scope_correction.py

Dr. Pham's A3 decision: contraindicated for tranylcypromine, whose PARNATE label lists SAM-e; correct the profile
rule "for that verified scope"; review the other MAOIs individually or document the class inference (ask 1).
Batch 2 raised the class-wide profile rule to contraindicated and labelled the class pair with label-level evidence.
An outside review (2026-11-11) found three consequences, each reproduced by the agent:
  1. the class pair's verifier-derived evidence tier became "established" for every MAOI;
  2. the class-inference caveat sat only in evidence_notes, which the interaction DB does not export;
  3. a contraindicated profile rule is hidden without a matching profile (build_final_db _INTERACTION_DISPLAY_MODE),
     so SAMe's conditional note disappeared.

This script records each scope where it can be expressed:
  - new exact pair DSI_TRANYLCYPROMINE_SAME (RxCUI 10734, verified on RxNav), Contraindicated, PARNATE label;
  - class pair DSI_MAOI_SAME stays Contraindicated (nothing lowered while ask 1 is pending), its exported mechanism
    states the class inference, and its evidence returns to what the inference supports (moderate);
  - profile rule RULE_IQM_SAME/maois returns to its published avoid (a profile that says only "MAOI" does not
    identify tranylcypromine), keeping the conditional note visible until G4 (batch 4).
NARDIL (phenelzine) contraindicates "serotoninergic agents" as a category (DailyMed setid 513a41d0, read
2026-11-11); whether SAMe falls under it is part of ask 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

CURATED = REPO / "scripts/data/curated_interactions/curated_interactions_v1.json"
RULES = REPO / "scripts/data/ingredient_interaction_rules.json"

REVIEW_FILE = "audits/clinical_review_20261111/DR_PHAM_REVIEW_20261111.md"
PARNATE = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b72d8187-dfcc-4ea0-b5e9-c0be95b69a27"
NARDIL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=513a41d0-37d4-4355-8a6d-a2c643bce6fa"
NCCIH_SAME = "https://www.nccih.nih.gov/health/sadenosyllmethionine-same-in-depth"
PENDING = (
    "The labels for phenelzine (NARDIL), isocarboxazid (MARPLAN) and selegiline (EMSAM, ZELAPAR) do not name SAMe "
    "(read 2026-11-11). NARDIL contraindicates concomitant serotoninergic agents as a category; whether SAMe falls "
    "under it is part of ask 1 to Dr. Pham."
)


def verification(note: str) -> dict:
    return {
        "status": "verified",
        "verified_at": "2026-11-11",
        "verified_with": {"rxnorm": True, "umls": True, "pubmed": True},
        "method": "agent_label_content_review_2026_11_11",
        "notes": note,
    }


def exact_pair(class_row: dict) -> dict:
    return {
        "id": "DSI_TRANYLCYPROMINE_SAME",
        "type": "Med-Sup",
        "agent1_name": "Tranylcypromine",
        "agent1_id": "10734",
        "agent2_name": class_row["agent2_name"],
        "agent2_id": class_row["agent2_id"],
        "severity": "Contraindicated",
        "interaction_effect_type": "Additive",
        "mechanism": (
            "SAMe raises serotonin activity. The tranylcypromine (PARNATE) label lists S-adenosyl-L-methionine "
            "(SAM-e) as contraindicated because combining it with tranylcypromine can cause serotonin syndrome."
        ),
        "management": (
            "Do not take SAMe with tranylcypromine. Do not stop or change tranylcypromine to use SAMe; your "
            "prescriber manages any medication change and the washout time."
        ),
        "source_urls": [PARNATE, NCCIH_SAME],
        "source_pmids": [],
        "verification": verification(
            "PARNATE sections 4.1 and 7 read on DailyMed; RxCUI 10734 (tranylcypromine, IN) checked on RxNav. "
            f"Severity decided by Dr. Pham (clinical review 2026-11-11, {REVIEW_FILE})."
        ),
        "evidence_basis": "label_regulatory",
        "clinical_confidence": "medium",
        "applies_to": "specific_drug",
        "evidence_notes": "PARNATE (tranylcypromine) sections 4.1 and 7 list SAM-e as contraindicated (serotonin syndrome).",
        "agent1_canonical_id": None,
        "agent2_canonical_id": class_row["agent2_canonical_id"],
        "direction": "harmful",
        "materiality": "presence",
    }


def class_pair(row: dict) -> None:
    assert row["severity"] == "Contraindicated" and row["evidence_basis"] == "label_regulatory"
    row.update({
        "mechanism": (
            "SAMe raises serotonin activity. The tranylcypromine (PARNATE) label lists SAMe as contraindicated because "
            "the combination can cause serotonin syndrome. The other MAOI labels do not name SAMe; for them this "
            "warning is applied by class inference while a clinician reviews each medicine. No study of SAMe with an "
            "MAOI was found."
        ),
        "source_urls": [PARNATE, NARDIL, NCCIH_SAME],
        "evidence_basis": "authoritative_review",
        "clinical_confidence": "low",
        "evidence_notes": (
            "Class record. Tranylcypromine has its own exact pair (DSI_TRANYLCYPROMINE_SAME). " + PENDING + " The "
            "class severity is kept, not lowered, until that decision."
        ),
        "verification": verification(
            "PARNATE and NARDIL labels read on DailyMed. Dr. Pham's contraindication covers tranylcypromine; the class "
            f"severity is the published value, kept pending ask 1 ({REVIEW_FILE})."
        ),
    })


def same_rule(sub: dict) -> None:
    assert sub["severity"] == "contraindicated"
    sub.update({
        "severity": "avoid",
        "evidence_level": "moderate",
        "action": (
            "If you take an MAOI, avoid SAMe. If your MAOI is tranylcypromine (Parnate), its label says the two must "
            "not be combined. Do not stop or change your MAOI to use SAMe; your prescriber manages any change and the "
            "washout time."
        ),
        "alert_headline": "Avoid combining with MAOIs",
        "alert_body": (
            "If you take an MAO inhibitor, avoid this product. SAMe raises serotonin activity; the tranylcypromine "
            "(Parnate) label lists it as contraindicated because of serotonin syndrome."
        ),
        "sources": [PARNATE, NARDIL, *sub["sources"][1:]],
        "clinical_review": {
            "reviewer": "Dr. Pham",
            "reviewed_at": "2026-11-11",
            "file": REVIEW_FILE,
            "notes": (
                "Her contraindication covers tranylcypromine, carried by the exact pair DSI_TRANYLCYPROMINE_SAME. A "
                "profile that says only MAOI does not identify the medicine, so this class rule keeps its published "
                "avoid: the other MAOIs are pending ask 1, and a contraindicated profile rule would hide SAMe's "
                "conditional note until G4."
            ),
        },
    })
    assert sub["sources"][0] == PARNATE and NCCIH_SAME in sub["sources"]


def curated(blob: dict) -> None:
    rows = blob["interactions"]
    assert not any(r["id"] == "DSI_TRANYLCYPROMINE_SAME" for r in rows)
    index = next(i for i, r in enumerate(rows) if r["id"] == "DSI_MAOI_SAME")
    class_pair(rows[index])
    rows.insert(index + 1, exact_pair(rows[index]))


def rules(blob: dict) -> None:
    rule = next(r for r in blob["interaction_rules"] if r["id"] == "RULE_IQM_SAME")
    same_rule(next(s for s in rule["drug_class_rules"] if s["drug_class_id"] == "maois"))


def edit(path: Path, fn) -> None:
    blob = data_batch.load(path)
    fn(blob)
    data_batch.save(path, blob)


if __name__ == "__main__":
    edit(CURATED, curated)
    edit(RULES, rules)
