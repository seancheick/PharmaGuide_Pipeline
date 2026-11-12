"""Batch 3a follow-up: betrixaban joins the DOAC class (identity, agent label review).

Run once from the repo root:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch3a_betrixaban_doac.py

class:doacs is defined by ATC B01AF (direct factor Xa inhibitors) and B01AE (direct thrombin inhibitors), taken by
mouth. Betrixaban (RxCUI 1927851, ingredient, active on RxNav 2026-11-11) is ATC B01AF on RxClass, and the BEVYXXA
label (NDA 208383, accessdata 2017 label, Reference ID 4115694, read by an agent 2026-11-11) calls it an oral factor
Xa inhibitor and a P-gp substrate (12.3) cleared mostly by CYP-independent hydrolysis. It was in class:anticoagulants
only, so the warfarin-addressed fallback findings (St. John's wort, glucosamine, cranberry, CoQ10, each with INR
text) reached it. As a DOAC it gets the DOAC St. John's wort finding instead, still avoid: the P-gp induction concern
is kept. The four injected direct thrombin inhibitors (argatroban, bivalirudin, desirudin, lepirudin) are ATC B01AE
but not oral, so they stay out of this class; their fallback text stays with question 7.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

CLASSES = REPO / "scripts/data/drug_classes.json"


def classes(blob: dict) -> None:
    doacs = blob["classes"]["class:doacs"]
    assert "1927851" not in doacs["member_rxcuis"] and "1927851" in blob["classes"]["class:anticoagulants"]["member_rxcuis"]
    pairs = sorted([*zip(doacs["member_names"], doacs["member_rxcuis"]), ("betrixaban", "1927851")])
    doacs["member_names"] = [name for name, _ in pairs]
    doacs["member_rxcuis"] = [rxcui for _, rxcui in pairs]
    doacs["notes"] = doacs["notes"] + (
        " Betrixaban added 2026-11-11 (ATC B01AF; BEVYXXA label: oral factor Xa inhibitor, P-gp substrate). The injected"
        " direct thrombin inhibitors (ATC B01AE) are not oral and are not members."
    )


if __name__ == "__main__":
    blob = data_batch.load(CLASSES)
    classes(blob)
    data_batch.save(CLASSES, blob)
