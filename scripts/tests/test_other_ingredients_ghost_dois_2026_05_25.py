"""Regression locks for ghost-DOI cleanup in other_ingredients.json.

Per `critical_no_hallucinated_citations` rule: identifiers must be
content-verified via live API; existence alone proves nothing.

Wave 6.X deep API sweep (orchestrator 2026-05-25) found 3 ghost
identifiers across 3 entries:

  - NHA_AVOCADO_SOY_UNSAPONIFIABLES — 10.1136/ard.60.2.171 (Crossref 404)
  - NHA_PARTIALLY_HYDROLYZED_GUAR_GUM — 10.1016/j.nut.2006.01.012 (Crossref 404)
  - NHA_SARCOSINE — 10.1016/j.biopsych.2004.09.009 (Crossref HTTP 200 BUT
    resolves to an editorial index entry in Biol Psychiatry 2004, NOT the
    intended sarcosine schizophrenia trial). Real DOI, wrong-topic
    content — qualifies as ghost per critical_no_hallucinated_citations.

Replacements (all content-verified via live PubMed efetch 2026-05-25,
none retracted):

| Entry | Replacement PMID | Title |
|---|---|---|
| NHA_AVOCADO_SOY_UNSAPONIFIABLES | 31328413 | Efficacy and safety of avocado-soybean unsaponifiables for hip and knee osteoarthritis: SR+MA (Simental-Mendía 2019 IJRD) |
| NHA_PARTIALLY_HYDROLYZED_GUAR_GUM | 16413751 | Role of PHGG in the treatment of irritable bowel syndrome (Giannini 2006 Nutrition) — same journal+year as ghost, likely the intended cite |
| NHA_PARTIALLY_HYDROLYZED_GUAR_GUM (secondary) | 26855665 | RCT: PHGG vs placebo in IBS (Niv 2016 Nutr Metab) — explicit IBS-D match per the notes |
| NHA_SARCOSINE | 17659263 | Sarcosine treatment for acute schizophrenia: RCT (Lane HY/Tsai GE 2008 Biol Psychiatry) |
"""

import json
from pathlib import Path

import pytest


OI_PATH = Path(__file__).resolve().parent.parent / "data" / "other_ingredients.json"


@pytest.fixture(scope="module")
def oi_db():
    return json.loads(OI_PATH.read_text())


def _find_entry(oi_db, entry_id):
    for entry in oi_db.get("other_ingredients", []):
        if isinstance(entry, dict) and entry.get("id") == entry_id:
            return entry
    return None


def _all_text(entry):
    parts = []
    def walk(v):
        if isinstance(v, str): parts.append(v)
        elif isinstance(v, list):
            for x in v: walk(x)
        elif isinstance(v, dict):
            for x in v.values(): walk(x)
    walk(entry)
    return " ".join(parts)


GHOSTS_TO_REMOVE = {
    "NHA_AVOCADO_SOY_UNSAPONIFIABLES":   ["10.1136/ard.60.2.171"],
    "NHA_PARTIALLY_HYDROLYZED_GUAR_GUM": ["10.1016/j.nut.2006.01.012"],
    "NHA_SARCOSINE":                     ["10.1016/j.biopsych.2004.09.009"],
}

REPLACEMENTS = {
    "NHA_AVOCADO_SOY_UNSAPONIFIABLES":   ["31328413"],
    "NHA_PARTIALLY_HYDROLYZED_GUAR_GUM": ["16413751", "26855665"],
    "NHA_SARCOSINE":                     ["17659263"],
}


@pytest.mark.parametrize("entry_id,ghost", [
    (eid, g) for eid, ghosts in GHOSTS_TO_REMOVE.items() for g in ghosts
])
def test_ghost_identifier_absent_from_entry(oi_db, entry_id, ghost):
    entry = _find_entry(oi_db, entry_id)
    assert entry is not None, f"{entry_id} missing"
    text = _all_text(entry)
    assert ghost not in text, (
        f"GHOST identifier {ghost!r} still present in {entry_id}. "
        f"Verified via Crossref API + PubMed esearch[aid] on 2026-05-25."
    )


@pytest.mark.parametrize("entry_id,pmid", [
    (eid, p) for eid, pmids in REPLACEMENTS.items() for p in pmids
])
def test_verified_replacement_pmid_present(oi_db, entry_id, pmid):
    entry = _find_entry(oi_db, entry_id)
    assert entry is not None
    text = _all_text(entry)
    assert pmid in text, (
        f"Verified replacement PMID {pmid} not found in {entry_id}. "
        f"Content-verified via live PubMed efetch 2026-05-25."
    )
