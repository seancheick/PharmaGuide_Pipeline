"""Regression contract for the 2026-06 batch-13 IQM audit (ashwagandha/
rice_protein/rhodiola/ginkgo/milk_thistle).

Verified: KSM-66 (root-only ~5%) != Shoden (root+leaf ~35%); withaferin A
(CID 265237), bilobalide (CID 73581) are marker compounds not the extract;
R. rosea (rosavins) != R. crenulata (salidroside-only); silymarin = constituent
not Silybum parent; phytosome != micellar != liposomal (distinct delivery);
liposomal ginkgo has ONE small human crossover for terpene lactones only
(PMID 35922794) so it stays below the validated EGb extract; rice protein is
lysine-limited (DIAAS axis). No sign-off forms in this batch.

Marker cleanup removes isolated single-compound names but KEEPS standardization
specs (e.g. "24% flavone glycosides 6% terpene lactones" = EGb 761 spec).
"""
import json
import os

import pytest

IQM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json")
EGB = "ginkgo biloba extract (24% flavone glycosides)"


@pytest.fixture(scope="module")
def iqm():
    with open(IQM_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _al(iqm, p, f):
    return {a.lower() for a in iqm[p]["forms"][f].get("aliases", [])}


# ── unspecified / liposomal inversions ───────────────────────────────────────
def test_score_inversions(iqm):
    assert iqm["rhodiola"]["forms"]["rhodiola (unspecified)"]["bio_score"] == 8
    assert iqm["ginkgo"]["forms"]["ginkgo (unspecified)"]["bio_score"] == 8
    # liposomal ginkgo below the validated EGb extract (single-study, terpene-only)
    assert iqm["ginkgo"]["forms"]["liposomal ginkgo"]["bio_score"] == 10
    assert iqm["ginkgo"]["forms"][EGB]["bio_score"] == 11


# ── marker compounds removed from extract forms (specs kept) ─────────────────
def test_ashwagandha_markers_off_extract(iqm):
    al = _al(iqm, "ashwagandha", "standard ashwagandha extract")
    for a in ["withaferin a", "withanolide a"]:
        assert a not in al
    assert "withanolides" in al  # standardization descriptor kept


def test_rhodiola_markers_off_extract(iqm):
    al = _al(iqm, "rhodiola", "rhodiola rosea extract (3% rosavins)")
    for a in ["rosavin", "rosavins", "salidroside", "tyrosol glucoside"]:
        assert a not in al


def test_ginkgo_markers_off_extract(iqm):
    al = _al(iqm, "ginkgo", EGB)
    for a in ["ginkgolide b", "bilobalide", "terpene lactones", "flavone glycosides"]:
        assert a not in al
    assert "24% flavone glycosides 6% terpene lactones" in al  # EGb spec kept


# ── brand / delivery / phytosome routing ─────────────────────────────────────
def test_ksm66_generics_to_standard_extract(iqm):
    ksm = _al(iqm, "ashwagandha", "KSM-66 ashwagandha")
    std = _al(iqm, "ashwagandha", "standard ashwagandha extract")
    for a in ["standardized ashwagandha", "high-potency ashwagandha", "full-spectrum ashwagandha"]:
        assert a not in ksm and a in std


def test_ginkgo_phytosome_off_liposomal(iqm):
    al = _al(iqm, "ginkgo", "liposomal ginkgo")
    assert "ginkgo phytosome" not in al and "ginkgo biloba, phosphatidylserine complex" not in al


def test_silymarin_off_parent_to_form(iqm):
    assert "silymarin" not in {a.lower() for a in iqm["milk_thistle"].get("aliases", [])}
    assert "silymarin" in _al(iqm, "milk_thistle", "standard silymarin")


def test_phytosome_off_standard_silymarin(iqm):
    std = _al(iqm, "milk_thistle", "standard silymarin")
    phyto = _al(iqm, "milk_thistle", "silymarin phytosome")
    for a in ["silybin phytosome complex", "silybum phytosome"]:
        assert a not in std and a in phyto


def test_rice_powder_to_general(iqm):
    assert "rice protein powder" not in _al(iqm, "rice_protein", "rice protein isolate")
    assert "rice protein powder" in _al(iqm, "rice_protein", "rice protein")
