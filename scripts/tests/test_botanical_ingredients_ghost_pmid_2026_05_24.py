"""Regression lock for ghost-PMID fix in botanical_ingredients.json.

Per `critical_no_hallucinated_citations` rule: PMIDs must be content-verified;
existence alone proves nothing. Subagent ab921a0a434c001a5 verified via PubMed
that the existing botanical_ingredients[horse_chestnut_seed].notes citation
of PMID 22592684 is a ghost reference:

  - PMID 22592684 actually = Hooper L, Summerbell CD, Thompson R.
    "Reduced or modified dietary fat for preventing cardiovascular disease."
    Cochrane Database Syst Rev, 2012. NOTHING to do with horse chestnut.

The correct citation for HCSE chronic venous insufficiency clinical evidence:

  - PMID 23152216 = Pittler MH, Ernst E. "Horse chestnut seed extract for
    chronic venous insufficiency." Cochrane Database Syst Rev. 2012 Nov 14;
    11:CD003230. DOI: 10.1002/14651858.CD003230.pub4. Verbatim conclusion:
    "The evidence presented suggests that HCSE is an efficacious and safe
    short-term treatment for CVI."

This is a clinical-data-integrity fix and ships separately from any IQM
scoring change so it has a clean rollback boundary.
"""

import json
from pathlib import Path

import pytest


BOT_PATH = Path(__file__).resolve().parent.parent / "data" / "botanical_ingredients.json"


@pytest.fixture(scope="module")
def bot_db():
    return json.loads(BOT_PATH.read_text())


def _find_horse_chestnut(bot_db):
    for entry in bot_db.get("botanical_ingredients", []):
        if isinstance(entry, dict) and entry.get("id") == "horse_chestnut_seed":
            return entry
    return None


def test_horse_chestnut_seed_entry_exists(bot_db):
    entry = _find_horse_chestnut(bot_db)
    assert entry is not None, "botanical_ingredients horse_chestnut_seed entry missing"


def test_horse_chestnut_seed_notes_does_not_cite_ghost_pmid(bot_db):
    """PMID 22592684 must NOT appear in horse_chestnut_seed notes.
    The actual PMID 22592684 is unrelated (dietary-fat Cochrane). Citing it
    here is a clinical-data-integrity defect per critical_no_hallucinated_
    citations."""
    entry = _find_horse_chestnut(bot_db)
    assert entry is not None
    notes = entry.get("notes", "")
    assert "22592684" not in notes, (
        f"GHOST PMID 22592684 still present in horse_chestnut_seed notes. "
        f"Actual PMID 22592684 is Hooper et al. 2012 dietary-fat Cochrane — "
        f"unrelated to horse chestnut. Replace with verified PMID 23152216."
    )


def test_horse_chestnut_seed_notes_cites_correct_cochrane_pmid(bot_db):
    """PMID 23152216 (Pittler & Ernst 2012 Cochrane HCSE for CVI) must be
    present as the corrected citation."""
    entry = _find_horse_chestnut(bot_db)
    assert entry is not None
    notes = entry.get("notes", "")
    assert "23152216" in notes, (
        "Corrected PMID 23152216 (Pittler & Ernst 2012 Cochrane: 'Horse "
        "chestnut seed extract for chronic venous insufficiency') missing "
        "from horse_chestnut_seed notes."
    )


def test_horse_chestnut_seed_notes_label_is_cochrane_review_not_rct(bot_db):
    """The original notes said 'RCT evidence' but PMID 23152216 is actually
    a Cochrane systematic review. The fix should update the descriptor too."""
    entry = _find_horse_chestnut(bot_db)
    assert entry is not None
    notes = entry.get("notes", "").lower()
    # the descriptor near the PMID should reflect 'Cochrane' / 'review' /
    # 'systematic review' rather than the misleading 'RCT' framing
    assert "cochrane" in notes or "systematic review" in notes, (
        "Notes should describe PMID 23152216 as a Cochrane / systematic review, "
        "not as a single RCT. The fix should correct both the PMID and the "
        "study-design label."
    )
