"""Regression contract: l_ornithine score was anchored to LOLA (L-ornithine
L-aspartate) PK, a DIFFERENT compound. Verified (PubChem CIDs 6262/76654/10220941):
free L-ornithine, ornithine HCl, and LOLA are distinct. The ~82% oral F is
LOLA-specific (Kircheis & Luth 2019, PMID 30706424; underlying bioequivalence
study PMID 16524681) and NOT transferable to free ornithine, whose absolute oral
F is unmeasured in humans (only plasma-rise/effect data exist — Sugino 2008
PMID 19083482). Demoted to the cationic-amino-acid class (cf. l-arginine hcl 12/0.55).
"""
import json
import os

import pytest

IQM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json")


@pytest.fixture(scope="module")
def iqm():
    with open(IQM_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def test_ornithine_demoted_off_lola_basis(iqm):
    f = iqm["l_ornithine"]["forms"]["l-ornithine standard"]
    # amino-acid class, conservative for unmeasured F (below arginine HCl's 12)
    assert f["bio_score"] == 11
    assert f["absorption_structured"]["value"] == 0.55
    assert f["absorption_structured"]["quality"] != "very_good"
    assert not f["absorption"].lower().startswith("good (~80")


def test_ornithine_notes_drop_lola_misattribution(iqm):
    notes = iqm["l_ornithine"]["forms"]["l-ornithine standard"]["notes"].lower()
    # the old free-ornithine "~82% (LOLA pharmacokinetics)" claim must be gone
    assert "~82% (lola pharmacokinetics" not in notes
    # honest framing present: F unmeasured; LOLA number not transferable
    assert "unmeasured" in notes
    assert "lola" in notes  # still referenced — but as the non-transferable source
