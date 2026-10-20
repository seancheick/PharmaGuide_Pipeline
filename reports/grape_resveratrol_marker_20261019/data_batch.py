"""Grape -> resveratrol marker contribution (October 19, 2026). Run from the repo root with $PG_PYTHON."""
import sys
sys.path.insert(0, "scripts")
import data_batch  # noqa: E402

PATH = "scripts/data/botanical_marker_contributions.json"
blob = data_batch.load(PATH)
assert "grape" not in blob["botanicals"]
blob["botanicals"]["grape"] = {
    "delivers": [{
        "marker_canonical_id": "resveratrol",
        "model": "standardization_required",
        "min_standardization_pct_required": 1.0,
        "default_contribution_mg_per_g": None,
        "evidence_source": "PubMed PMID:12926863 — Direct HPLC analysis of quercetin and trans-resveratrol in red wine, grape, and winemaking byproducts.",
        "evidence_url": "https://pubmed.ncbi.nlm.nih.gov/12926863/",
        "evidence_id": "PMID:12926863",
        "evidence_keyword_coverage": 1.0,
        "fetched_at": "2026-10-19T23:30:00+00:00",
        "standardization_keywords": ["trans-resveratrol", "resveratrol"],
        "notes": ("Trans-resveratrol is measured by HPLC in red wine, grape (Vitis vinifera) skins and "
                  "winemaking byproducts (PMID:12926863). Red-wine grape extracts sold as supplements declare a "
                  "standardized percentage (BioVin Advanced: 5%). Credit only when the label declares a "
                  "trans-resveratrol percentage of at least 1%; the identity stays grape."),
    }],
    "source_db": "botanical_ingredients",
}
data_batch.save(PATH, blob)
