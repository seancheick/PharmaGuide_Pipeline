"""Regression locks for ghost-DOI cleanup in harmful_additives.json.

Per `critical_no_hallucinated_citations` rule: identifiers must be
content-verified via live API; existence alone proves nothing.

Wave 6.X deep API sweep (orchestrator, 2026-05-25) found 13 ghost
identifiers across 11 entries — either Crossref HTTP 404 (DOI does not
exist) or Crossref HTTP 200 with WRONG-TOPIC content (real DOI but
resolves to an article about an unrelated subject — a content-ghost).

Each replacement PMID below was content-verified via live PubMed efetch
on 2026-05-25 — the article title matches the claimed topic keywords.
None are retracted. Subagent proposals were re-verified independently
by the orchestrator before any data edit.

Ghost inventory + verified replacements:

| Entry | Ghost (status) | Replacement PMID | Verified Title |
|---|---|---|---|
| ADD_PROPYLENE_GLYCOL | 10.1542/peds.2013-3873 (Crossref 404) | 34670216 | MR Spectroscopy Shows Long Propylene Glycol Half-Life in Neonatal Brain |
| ADD_PROPYLENE_GLYCOL | 10.1016/j.fct.2017.04.043 (content-ghost — real DOI = platinum nanoparticles) | 23064775 | Safety assessment of propylene glycol, tripropylene glycol, and PPGs as used in cosmetics |
| ADD_SODIUM_NITRITE | 10.1016/j.meatsci.2018.05.032 (Crossref 404) | 32188080 | Nitrates/Nitrites in Food-Risk for Nitrosative Stress and Benefits |
| ADD_SODIUM_NITRATE | 10.1016/j.meatsci.2018.05.032 (shared ghost) | 32188080 | (same as above) |
| ADD_SUGAR_ALCOHOLS | 10.3390/nu11040644 (Crossref 404) | 28710145 | A Systematic Review of the Effects of Polyols on Gastrointestinal Health and Irritable Bowel Syndrome |
| ADD_SUGAR_ALCOHOLS | 10.1111/j.1365-2036.2010.04227.x (Crossref 404) | 27840639 | Gastrointestinal Disturbances Associated with the Consumption of Sugar Alcohols ... Xylitol |
| ADD_POLYSORBATE80 | 10.1038/s41467-025-45123-4 (Crossref 404) | 40730751 | Maternal emulsifier consumption alters offspring early-life microbiota and goblet cell function |
| ADD_YELLOW5 | 10.1021/jf204398u (Crossref 404) | 26404013 | Health safety issues of synthetic food colorants |
| ADD_YELLOW6 | 10.1021/jf204398u (shared ghost) | 26404013 | (primary) + 31539566 (secondary: FD&C Yellow No. 6 28-day toxicity) |
| ADD_SYNTHETIC_B_VITAMINS | 10.1016/j.jnutbio.2019.108365 (Crossref 404) | 25820384 | Cobalamin coenzyme forms are not likely to be superior to cyano- and hydroxyl-cobalamin |
| ADD_SYNTHETIC_B_VITAMINS | 10.3390/nu12020523 (content-ghost — real DOI = andrographolide steatohepatitis) | 22529856 | Circulating unmetabolized folic Acid: relationship to folate status and effect of supplementation |
| ADD_MSG | 10.1007/s00726-018-2594-9 (Crossref 404) | 24927698 | Is there a relationship between dietary MSG and obesity in animals or humans? |
| ADD_CASSAVA_DEXTRIN | 10.1038/s41586-018-0061-4 (Crossref 404) | 30765332 | The Food Additive Maltodextrin Promotes Endoplasmic Reticulum Stress-Driven Mucus Depletion |

PER-ENTRY VERIFICATION CADENCE preserved: every replacement PMID
independently content-verified by orchestrator via live PubMed efetch
on 2026-05-25 — not bulk-imported, no subagent claim accepted blindly.

EFSA DOIs (3 entries: ADD_ACRYLAMIDE, ADD_ASPARTAME, ADD_BLUE2) are
KEPT — they appear "broken" in PubMed esearch because EFSA Scientific
Opinions are not PubMed-indexed, but they ARE real European regulatory
documents verified via Crossref HTTP 200. Not ghosts.
"""

import json
from pathlib import Path

import pytest


HA_PATH = Path(__file__).resolve().parent.parent / "data" / "harmful_additives.json"


@pytest.fixture(scope="module")
def ha_db():
    return json.loads(HA_PATH.read_text())


def _find_entry(ha_db, entry_id):
    for entry in ha_db.get("harmful_additives", []):
        if isinstance(entry, dict) and entry.get("id") == entry_id:
            return entry
    return None


def _all_text(entry):
    """Concatenate all string fields of an entry for ghost-presence checks."""
    parts = []
    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
    walk(entry)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Ghost identifiers that MUST be removed (Crossref 404 OR wrong-topic)
# ---------------------------------------------------------------------------

GHOSTS_TO_REMOVE = {
    "ADD_PROPYLENE_GLYCOL":     ["10.1542/peds.2013-3873", "10.1016/j.fct.2017.04.043"],
    "ADD_SODIUM_NITRITE":       ["10.1016/j.meatsci.2018.05.032"],
    "ADD_SODIUM_NITRATE":       ["10.1016/j.meatsci.2018.05.032"],
    "ADD_SUGAR_ALCOHOLS":       ["10.3390/nu11040644", "10.1111/j.1365-2036.2010.04227.x"],
    "ADD_POLYSORBATE80":        ["10.1038/s41467-025-45123-4"],
    "ADD_YELLOW5":              ["10.1021/jf204398u"],
    "ADD_YELLOW6":              ["10.1021/jf204398u"],
    "ADD_SYNTHETIC_B_VITAMINS": ["10.1016/j.jnutbio.2019.108365", "10.3390/nu12020523"],
    "ADD_MSG":                  ["10.1007/s00726-018-2594-9"],
    "ADD_CASSAVA_DEXTRIN":      ["10.1038/s41586-018-0061-4"],
    "ADD_MALTODEXTRIN":         ["22394256"],  # +1 ghost PMID found in post-fix re-sweep
}


@pytest.mark.parametrize("entry_id,ghost", [
    (eid, g) for eid, ghosts in GHOSTS_TO_REMOVE.items() for g in ghosts
])
def test_ghost_identifier_absent_from_entry(ha_db, entry_id, ghost):
    entry = _find_entry(ha_db, entry_id)
    assert entry is not None, f"{entry_id} not found in harmful_additives.json"
    text = _all_text(entry)
    assert ghost not in text, (
        f"GHOST identifier {ghost!r} still present in {entry_id}. "
        f"Verified ghost via Crossref API on 2026-05-25 — must be replaced."
    )


# ---------------------------------------------------------------------------
# Verified replacement PMIDs that MUST be present
# ---------------------------------------------------------------------------

REPLACEMENTS = {
    "ADD_PROPYLENE_GLYCOL":     ["34670216", "23064775"],
    "ADD_SODIUM_NITRITE":       ["32188080"],
    "ADD_SODIUM_NITRATE":       ["32188080"],
    "ADD_SUGAR_ALCOHOLS":       ["28710145", "27840639"],
    "ADD_POLYSORBATE80":        ["40730751"],
    "ADD_YELLOW5":              ["26404013"],
    "ADD_YELLOW6":              ["26404013"],
    "ADD_SYNTHETIC_B_VITAMINS": ["25820384", "22529856"],
    "ADD_MSG":                  ["24927698"],
    "ADD_CASSAVA_DEXTRIN":      ["30765332"],
    # ADD_MALTODEXTRIN ghost PMID 22394256 was a typo collapsing two real
    # papers under one fake PMID. Replace with both real PMIDs:
    #   23251695 = Nickerson 2012 PLoS One AIEC adhesion paper
    #   25738413 = Nickerson 2015 Gut Microbes intestinal anti-microbial paper
    "ADD_MALTODEXTRIN":         ["23251695", "25738413"],
}


@pytest.mark.parametrize("entry_id,pmid", [
    (eid, p) for eid, pmids in REPLACEMENTS.items() for p in pmids
])
def test_verified_replacement_pmid_present(ha_db, entry_id, pmid):
    entry = _find_entry(ha_db, entry_id)
    assert entry is not None, f"{entry_id} not found"
    text = _all_text(entry)
    assert pmid in text, (
        f"Verified replacement PMID {pmid} not found in {entry_id}. "
        f"Content-verified via live PubMed efetch 2026-05-25."
    )


# ---------------------------------------------------------------------------
# EFSA DOIs MUST be kept (real regulatory documents, not ghosts)
# ---------------------------------------------------------------------------

EFSA_KEEP = {
    "ADD_ACRYLAMIDE": "10.2903/j.efsa.2015.4104",
    "ADD_ASPARTAME":  "10.2903/j.efsa.2013.3496",
    "ADD_BLUE2":      "10.2903/j.efsa.2014.3768",
}


@pytest.mark.parametrize("entry_id,doi", list(EFSA_KEEP.items()))
def test_efsa_doi_preserved(ha_db, entry_id, doi):
    """EFSA Scientific Opinion DOIs are real EU regulatory documents
    verified via Crossref HTTP 200, even though PubMed doesn't index
    them. Must NOT be deleted as part of ghost cleanup."""
    entry = _find_entry(ha_db, entry_id)
    assert entry is not None
    assert doi in _all_text(entry), (
        f"EFSA DOI {doi} missing from {entry_id} — these are real "
        f"regulatory documents and must be preserved."
    )
