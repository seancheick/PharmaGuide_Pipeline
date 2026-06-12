"""Regression contract for the 2026-06 batch-10 IQM audit (l_ornithine/
d_aspartic_acid/l_tryptophan/gaba/beta-alanine).

Verified: tryptophan brain delivery LAT1/LNAA-gated (PMID 12614332); oral-GABA
BBB uncertain + liposomal unsupported (PMID 26500584); CarnoSyn = generic
beta-alanine, same molecule CID 239, premium is NSF/RCT provenance not absorption
(PMID 27797728); SR beta-alanine same AUC, lower Cmax (Décombaz 2012 PMID 22139410);
D-aspartic acid no human F% PK + contradictory testosterone RCTs (PMID 24074738).
"""
import json
import os

import pytest

IQM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json")


@pytest.fixture(scope="module")
def iqm():
    with open(IQM_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _form(iqm, p, f):
    return iqm[p]["forms"][f]


def _al(iqm, p, f):
    return {a.lower() for a in _form(iqm, p, f).get("aliases", [])}


# ── score corrections (all non-signed-off; natural=false so score == bio) ────
SCORE_TARGETS = [
    ("l_tryptophan", "l-tryptophan powder", 10),       # systemic/brain delivery limited (val 0.4 tier)
    ("gaba", "liposomal gaba", 6),                       # BBB unproven; = the signed-off plain-GABA tier
    ("beta-alanine", "carnosyn beta-alanine", 14),       # = generic (provenance, not absorption)
]


@pytest.mark.parametrize("parent,form,expected", SCORE_TARGETS)
def test_bio_score_corrected(iqm, parent, form, expected):
    f = _form(iqm, parent, form)
    assert f["bio_score"] == expected
    assert f["score"] == min(18, f["bio_score"] + (3 if f.get("natural") else 0))


def test_carnosyn_equals_generic_beta_alanine(iqm):
    # same molecule -> same absorption score (SR also 14: same AUC, lower Cmax only)
    cs = _form(iqm, "beta-alanine", "carnosyn beta-alanine")["bio_score"]
    gen = _form(iqm, "beta-alanine", "beta-alanine powder")["bio_score"]
    sr = _form(iqm, "beta-alanine", "sr carnosyn beta-alanine")["bio_score"]
    assert cs == gen == sr == 14


def test_liposomal_gaba_not_above_plain(iqm):
    lipo = _form(iqm, "gaba", "liposomal gaba")["bio_score"]
    plain = _form(iqm, "gaba", "gaba powder")["bio_score"]
    assert lipo <= plain


# ── marketing alias cleanup ──────────────────────────────────────────────────
def test_gaba_marketing_aliases_removed(iqm):
    al = _al(iqm, "gaba", "liposomal gaba")
    for a in ["nano gaba", "encapsulated gaba", "advanced delivery gaba"]:
        assert a not in al


def test_carnosine_precursor_off_carnosyn(iqm):
    assert "carnosine precursor" not in _al(iqm, "beta-alanine", "carnosyn beta-alanine")
