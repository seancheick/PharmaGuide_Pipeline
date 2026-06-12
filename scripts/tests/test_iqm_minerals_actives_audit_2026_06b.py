"""Regression contract for the 2026-06 batch-2 IQM audit (minerals + sports actives).

Verified against the file's own honesty_rule (bio_score = absorption for systemic
actives) and content-confirmed PK (PMIDs 22971354 buffered-creatine equivalence,
19228401 CEE→creatinine, 24272966 D-ribose absorption; NIH ODS Mg/Zn/Se).

Invariant: score == bio_score + 3*natural (capped 18).
"""
import json
import os

import pytest

IQM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json")


@pytest.fixture(scope="module")
def iqm():
    with open(IQM_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _form(iqm, parent, form):
    return iqm[parent]["forms"][form]


def _al(iqm, parent, form):
    return {a.lower() for a in _form(iqm, parent, form).get("aliases", [])}


# ── 1. creatine salts are F-equivalent to monohydrate (dissociate to same ion);
#       CEE is genuinely poor (degrades to creatinine) ──────────────────────────
SCORE_TARGETS = [
    ("creatine_monohydrate", "buffered creatine monohydrate", 13),
    ("creatine_monohydrate", "creatine nitrate", 13),
    ("creatine_monohydrate", "creatine hydrochloride", 13),
    ("creatine_monohydrate", "creatine citrate", 13),
    ("creatine_monohydrate", "creatine magnesium chelate", 13),
    ("creatine_monohydrate", "dicreatine malate", 12),       # F-plausible, no human PK
    ("creatine_monohydrate", "creatine ethyl ester", 4),     # degrades to creatinine
    ("astaxanthin", "unspecified astaxanthin", 10),          # unknown matrix -> below disclosed
    ("hmb", "hmb free acid (hmb-fa)", 13),                   # equal total F to HMB-Ca (kinetics only)
]


@pytest.mark.parametrize("parent,form,expected", SCORE_TARGETS)
def test_bio_score_corrected(iqm, parent, form, expected):
    assert _form(iqm, parent, form)["bio_score"] == expected


@pytest.mark.parametrize("parent,form,_", SCORE_TARGETS)
def test_score_invariant(iqm, parent, form, _):
    f = _form(iqm, parent, form)
    assert f["score"] == min(18, f["bio_score"] + (3 if f.get("natural") else 0))


# ── 2. natural-bonus misapplied to a purified crystalline ingredient ──────────
def test_d_ribose_not_natural(iqm):
    f = _form(iqm, "d_ribose", "d-ribose powder")
    assert f["natural"] is False           # purified/fermentation crystalline, not a natural-source matrix
    assert f["bio_score"] == 14            # absorption ~95% justifies the bio_score on its own
    assert f["score"] == 14


# ── 3. identity-error aliases removed ─────────────────────────────────────────
def test_astaxanthin_drops_broad_carotenoid(iqm):
    al = _al(iqm, "astaxanthin", "natural astaxanthin (haematococcus pluvialis)")
    assert "natural carotenoid" not in al
    assert "natural carotenoid supplement" not in al


def test_selenomethionine_drops_generic_organic(iqm):
    assert "organic selenium" not in _al(iqm, "selenium", "selenomethionine")


def test_hip_drops_liver_source(iqm):
    al = _al(iqm, "iron", "heme iron polypeptide")
    assert "beef liver iron" not in al
    assert "liver iron" not in al


def test_selenoexcell_off_parent(iqm):
    assert "selenoexcell" not in {a.lower() for a in iqm["selenium"].get("aliases", [])}
    assert "selenoexcell" in _al(iqm, "selenium", "selenized yeast")  # still routes here


# ── 4. alias re-routing to correct form ───────────────────────────────────────
def test_ferronyl_carbonyl_to_carbonyl_iron(iqm):
    assert "ferronyl carbonyl iron" not in {a.lower() for a in iqm["iron"].get("aliases", [])}
    assert "ferronyl carbonyl iron" in _al(iqm, "iron", "carbonyl iron")


def test_hmb_monohydrate_to_ca_salt(iqm):
    assert "beta-hydroxy beta-methylbutyrate monohydrate" not in _al(iqm, "hmb", "hmb free acid (hmb-fa)")
    assert "beta-hydroxy beta-methylbutyrate monohydrate" in _al(iqm, "hmb", "hmb calcium salt (hmb-ca)")


def test_slippery_elm_broad_powder_to_unspecified(iqm):
    inner = _al(iqm, "slippery_elm", "inner bark powder")
    uns = _al(iqm, "slippery_elm", "bark powder (unspecified)")
    for a in ["slippery elm bark powder", "slippery elm powder"]:
        assert a not in inner
        assert a in uns


def test_zinc_arginate_to_chelate(iqm):
    assert "zinc arginate" not in _al(iqm, "zinc", "zinc (unspecified)")
    assert "zinc arginate" in _al(iqm, "zinc", "zinc amino acid chelate")


# ── 5. absorption display strings no longer overstate/conflict with ODS ───────
def test_absorption_strings_honest(iqm):
    assert _form(iqm, "magnesium", "magnesium glycinate")["absorption"] != "80%+"
    assert _form(iqm, "zinc", "zinc picolinate")["absorption"] != "high (87%)"
    # selenite/selenate are WELL absorbed (~90% ODS); old strings implied poor absorption
    assert _form(iqm, "selenium", "sodium selenite")["absorption"] != "50%"
    assert _form(iqm, "selenium", "sodium selenate")["absorption"] != "45%"


def test_d_ribose_note_not_outcome_justified(iqm):
    assert "well-documented clinical benefits" not in _form(iqm, "d_ribose", "d-ribose powder")["notes"].lower()
