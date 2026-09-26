"""Curated drug-supplement pairs cite sources about the pair they describe.

A real PMID about the right ingredient but the wrong topic is a ghost reference.
Receipts: scripts/audits/pending_items_20260926/research.md.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
PAIRS = {
    entry["id"]: entry
    for entry in json.loads((DATA / "curated_interactions" / "curated_interactions_v1.json").read_text())["interactions"]
}


def test_garlic_warfarin_does_not_cite_the_allicin_antimicrobial_paper():
    """PMID 10594976 (Ankri & Mirelman 1999) is "Antimicrobial properties of
    allicin from garlic"; it says nothing about warfarin or bleeding. NCCIH's
    garlic page, which states the bleeding risk with anticoagulants, remains."""
    pair = PAIRS["DSI_WAR_GARLIC"]
    assert "10594976" not in pair.get("source_pmids", [])
    assert not any("10594976" in url for url in pair.get("source_urls", []))
    assert any("nccih.nih.gov" in url for url in pair["source_urls"])
