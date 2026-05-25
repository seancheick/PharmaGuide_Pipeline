"""Regression locks for 2 ghost-PMID fixes in botanical_ingredients.json.

Per `critical_no_hallucinated_citations` rule: PMIDs must be content-verified
via the live PubMed API; existence alone proves nothing. Wave 6.X deep-sweep
verification (orchestrator, 2026-05-25) found 2 additional ghost PMIDs:

GHOST 1 — botanical_ingredients[mucuna_pruriens].notes
  - cited: PMID 14737007 (Ayurvedic Kapikacchu for L-DOPA / Parkinson's)
  - reality: PMID 14737007 does NOT exist in PubMed (live esearch [uid]
    returned empty for both this and the broken DOI lookup)
  - replacement: PMID 28679598 = Cilia R, et al. "Mucuna pruriens in Parkinson
    disease: A double-blind, randomized, controlled, crossover study."
    Neurology 2017. Content-verified 2026-05-25: title matches both 'mucuna'
    and 'parkinson' keywords. Gold-standard RCT for the L-DOPA mechanism
    claim. NOT retracted.

GHOST 2 — botanical_ingredients[sage_leaf_extract].notes
  - cited: PMID 16988880 (RCT for cognitive function and menopausal hot flashes)
  - reality: PMID 16988880 does NOT exist in PubMed (live esearch [uid] empty)
  - replacement: PMID 24836739 = Lopresti AL. "Systematic review of clinical
    trials assessing pharmacological properties of Salvia species on memory,
    cognitive impairment and Alzheimer's disease." CNS Neurosci Ther 2014.
    Content-verified 2026-05-25: title matches 'salvia', 'memory', and
    'cognit' keywords. Systematic-review evidence for the cognitive claim
    in the IQM notes. NOT retracted.
  - Optional secondary citation for the menopausal hot-flash claim:
    PMID 37489230 = Mahmoudi M, et al. "The Effect of Salvia Officinalis on
    Hot Flashes in Postmenopausal Women: A Systematic Review and
    Meta-Analysis." Int J Community Based Nurs Midwifery 2023. Verified
    2026-05-25; ships if and only if dev wants both citations preserved.

Per CLAUDE.md "no batch fixes on data files": each ghost is one atomic
clinical-data-integrity commit. This test file locks both via two
independent tests so either commit can land separately.
"""

import json
from pathlib import Path

import pytest


BOT_PATH = Path(__file__).resolve().parent.parent / "data" / "botanical_ingredients.json"


@pytest.fixture(scope="module")
def bot_db():
    return json.loads(BOT_PATH.read_text())


def _find_entry(bot_db, entry_id):
    for entry in bot_db.get("botanical_ingredients", []):
        if isinstance(entry, dict) and entry.get("id") == entry_id:
            return entry
    return None


# ===========================================================================
# Ghost 1: mucuna_pruriens cites PMID 14737007 (does not exist)
# Fix: replace with verified PMID 28679598 (Cilia 2017 Neurology RCT)
# ===========================================================================


def test_mucuna_pruriens_entry_exists(bot_db):
    entry = _find_entry(bot_db, "mucuna_pruriens")
    assert entry is not None, "botanical_ingredients mucuna_pruriens entry missing"


def test_mucuna_pruriens_notes_does_not_cite_ghost_pmid_14737007(bot_db):
    """PMID 14737007 does NOT exist in PubMed. Verified via direct esearch
    [uid] on 2026-05-25 — returned empty result. Must be removed."""
    entry = _find_entry(bot_db, "mucuna_pruriens")
    assert entry is not None
    notes = entry.get("notes", "")
    assert "14737007" not in notes, (
        f"GHOST PMID 14737007 still in mucuna_pruriens notes. "
        f"Verified 2026-05-25 via live PubMed esearch [uid] — does not exist. "
        f"Replace with verified PMID 28679598 (Cilia 2017 Neurology RCT)."
    )


def test_mucuna_pruriens_notes_cites_verified_replacement_pmid_28679598(bot_db):
    """PMID 28679598 = Cilia 2017 'Mucuna pruriens in Parkinson disease:
    A double-blind, randomized, controlled, crossover study' (Neurology).
    Content-verified 2026-05-25 via live PubMed API. Supports the original
    L-DOPA / Parkinson's claim with gold-standard RCT evidence."""
    entry = _find_entry(bot_db, "mucuna_pruriens")
    assert entry is not None
    notes = entry.get("notes", "")
    assert "28679598" in notes, (
        "Verified replacement PMID 28679598 (Cilia 2017 Neurology RCT) "
        "missing from mucuna_pruriens notes."
    )


# ===========================================================================
# Ghost 2: sage_leaf_extract cites PMID 16988880 (does not exist)
# Fix: replace with verified PMID 24836739 (Lopresti 2014 CNS Neurosci Ther SR)
# ===========================================================================


def test_sage_leaf_extract_entry_exists(bot_db):
    entry = _find_entry(bot_db, "sage_leaf_extract")
    assert entry is not None, "botanical_ingredients sage_leaf_extract entry missing"


def test_sage_leaf_extract_notes_does_not_cite_ghost_pmid_16988880(bot_db):
    """PMID 16988880 does NOT exist in PubMed. Verified via direct esearch
    [uid] on 2026-05-25 — returned empty result. Must be removed."""
    entry = _find_entry(bot_db, "sage_leaf_extract")
    assert entry is not None
    notes = entry.get("notes", "")
    assert "16988880" not in notes, (
        f"GHOST PMID 16988880 still in sage_leaf_extract notes. "
        f"Verified 2026-05-25 via live PubMed esearch [uid] — does not exist. "
        f"Replace with verified PMID 24836739 (Lopresti 2014 SR)."
    )


def test_sage_leaf_extract_notes_cites_verified_replacement_pmid_24836739(bot_db):
    """PMID 24836739 = Lopresti AL 2014 'Systematic review of clinical
    trials assessing pharmacological properties of Salvia species on memory,
    cognitive impairment and Alzheimer's disease' (CNS Neurosci Ther).
    Content-verified 2026-05-25 via live PubMed API. Supports the cognitive
    claim in the original notes via systematic-review evidence."""
    entry = _find_entry(bot_db, "sage_leaf_extract")
    assert entry is not None
    notes = entry.get("notes", "")
    assert "24836739" in notes, (
        "Verified replacement PMID 24836739 (Lopresti 2014 SR) missing "
        "from sage_leaf_extract notes."
    )
