"""Batch 1: add the L-cystine IQM parent (identity receipts in research.md)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import data_batch  # noqa: E402

PATH = Path(__file__).resolve().parents[2] / "data" / "ingredient_quality_map.json"
blob = data_batch.load(PATH)
assert "l_cystine" not in blob
blob["l_cystine"] = {
    "standard_name": "L-Cystine",
    "category": "amino_acids",
    "description": "Disulfide dimer of two L-cysteine molecules (PubChem CID 67678). A distinct compound from L-cysteine and N-acetylcysteine.",
    "cui": "C0010682",
    "rxcui": "3036",
    "forms": {
        "l-cystine (unspecified)": {
            "bio_score": 5,
            "absorption": "unknown (applicable human absolute fraction unresolved)",
            "consumer_note": "L-cystine is two L-cysteine molecules joined by a disulfide bond. It is a different compound from L-cysteine and N-acetylcysteine.",
            "consumer_note_review": {
                "by": "Claude identity curation (agent review); no clinical approval",
                "date": "2026-10-31",
            },
            "notes": "Identity only: PubChem CID 67678, CAS 56-89-3, GSRS UNII 48TCX9A1VT (absolute stereochemistry), RxNorm 3036, UMLS C0010682. No reviewed source establishes a human absolute fraction for supplemental L-cystine, so the score uses the conservative unknown-absorption amino acid anchor. An L-cystine amount is not an L-cysteine or NAC amount.",
            "aliases": ["l-cystine", "cystine", "l cystine"],
            "dosage_importance": 1.0,
            "absorption_structured": {"value": None, "range_low": None, "range_high": None, "quality": "unknown"},
        }
    },
    "match_rules": {
        "priority": 0,
        "match_mode": "alias_and_fuzzy",
        "exclusions": [],
        "parent_id": None,
        "confidence": "high",
        "negative_match_terms": ["acetyl", "cysteine"],
    },
    "category_enum": "amino_acids",
    "data_quality": {
        "completeness": 0.2,
        "review_status": "stub",
        "last_reviewed_at": "2026-10-31",
        "research_status": "unverified",
    },
    "external_ids": {"unii": "48TCX9A1VT", "cas": "56-89-3", "pubchem_cid": 67678},
    "aliases": [],
}
print(data_batch.save(PATH, blob))
