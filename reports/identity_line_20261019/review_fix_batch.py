#!/usr/bin/env python3
"""Data batch after review: an evidence record the label-named rule needs, one stray ElevATP alias.

Receipts in research.md. Run once from the repo root with $PG_PYTHON.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from data_batch import load, save  # noqa: E402

path = REPO / "scripts" / "data" / "literature_evidence_records.json"
blob = load(path)
records = blob["literature_evidence_records"]
assert not any(r["canonical_id"] == "green_bell_pepper" for r in records)
records.append({
    "canonical_id": "green_bell_pepper",
    "material_form": "Green bell pepper (Capsicum annuum, sweet cultivar) fruit powder or juice in a whole-food blend",
    "search_query": (
        '("bell pepper"[tiab] OR "sweet pepper"[tiab] OR "green pepper"[tiab]) AND '
        '(randomized controlled trial[pt] OR clinical trial[pt]); '
        '"Capsicum annuum"[tiab] AND (randomized controlled trial[pt] OR clinical trial[pt])'
    ),
    "search_date": "2026-10-19",
    "databases_searched": ["PubMed"],
    "records_screened": 13,
    "qualifying_human_studies": [],
    "effect_direction": "not_efficacy_relevant",
    "population_context": "not applicable (food matrix)",
    "studied_dose_exposure": {},
    "applicability_decision": (
        "Identity classification, not a literature claim: green bell pepper in these labels is a "
        "vegetable powder inside a fruit-and-vegetable blend. A bounded, not exhaustive PubMed screen "
        "(13 records) found no single-ingredient supplement trial; the hits were bell pepper juice "
        "added to yoga therapy (PMID 28917374), capsaicin, capsinoid or paprika-oleoresin studies of "
        "hot or sweet Capsicum extracts, child vegetable-acceptance trials and agronomy."
    ),
    "applicability_status": "whole_food_matrix_not_efficacy_relevant",
    "verification_result": "identity_classification_no_literature_claim",
    "verification_provenance": {
        "verified_by": "identity straight line 2026-10-19: live PubMed esearch/esummary screen of all 13 records",
        "verified_at": "2026-10-19",
        "all_pmids_verified": True,
        "retractions_found": False,
    },
})
# Every record in the file is verified (this one by identity classification).
assert blob["_metadata"]["verified_records_count"] == len(records) - 1
blob["_metadata"]["verified_records_count"] = len(records)
save(path, blob)

# ElevATP is ancient peat + apple extract (FutureCeuticals), not shilajit: the "&" spelling of
# the alias moved in alias_batch.py still pointed at the shilajit fulvic acid form.
iqm_path = REPO / "scripts" / "data" / "ingredient_quality_map.json"
iqm = load(iqm_path)
fulvic = iqm["shilajit"]["forms"]["fulvic acid"]["aliases"]
assert "ancient peat & apple extract" in fulvic
fulvic.remove("ancient peat & apple extract")
save(iqm_path, iqm)
oi_path = REPO / "scripts" / "data" / "other_ingredients.json"
oi = load(oi_path)
elevatp = next(e for e in oi["other_ingredients"] if e["id"] == "PII_ELEVATP_BRANDED_BLEND")
assert "ancient peat & apple extract" not in elevatp["aliases"]
elevatp["aliases"].append("ancient peat & apple extract")
save(oi_path, oi)
