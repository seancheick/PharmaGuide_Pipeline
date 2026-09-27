"""Standardized-botanical sources cite real papers about the entry they support.

A PMID that does not exist is a fabricated identifier. Receipts:
scripts/audits/pending_items_20260926/research.md.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
ENTRIES = {
    entry["id"]: entry
    for entry in json.loads((DATA / "standardized_botanicals.json").read_text())["standardized_botanicals"]
}


def test_ginger_cites_the_marx_2017_review_not_a_nonexistent_pmid():
    """PMID 28200047 does not exist in PubMed. The source line named Marx et al.
    2017; that paper is PMID 25848702 (Crit Rev Food Sci Nutr), a narrative
    review of ginger's mechanism in chemotherapy-induced nausea, not a
    systematic review."""
    sources = " ".join(ENTRIES["ginger_extract"]["sources"])
    assert "28200047" not in sources
    assert "PMID 25848702" in sources
    assert "systematic review" not in sources
