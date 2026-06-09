"""Regression contract for the 2026-06 batch-4 IQM audit (minerals + CoQ10 + inositol).

Verified against NIH ODS (Cu/Mn/Cr/I/K/Mo/B: no comparative form bioavailability
data; minerals poorly absorbed) and PK (CoQ10 low/limited all forms — PMID 16551570;
ubiquinol edge contested — PMID 32380795; D-pinitol CID 164619 != DCI).
Invariant: score == bio_score + 3*natural.
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


# ── 1. mineral-chelate premiums unsupported (ODS: no comparative form data) +
#       CoQ10 crystal-free not a max-absorption ingredient + DCI=MI on absorption ──
SCORE_TARGETS = [
    ("copper", "copper bisglycinate", 11),          # ODS: no Cu form comparison
    ("copper", "copper picolinate", 10),            # no human PK
    ("manganese", "manganese bisglycinate", 11),    # val 0.08; ODS: 1-5%, no form data
    ("manganese", "manganese amino acid chelate", 11),
    ("molybdenum", "molybdenum glycinate", 12),     # = sodium molybdate (the evidence form)
    ("potassium", "potassium glycinate", 11),       # was top with lowest value
    # NOTE: CoQ10 ubiquinol crystal-free left at 15 — Dr Pham "C1 sign-off
    # (pd-respect): bio_score=15 retained for clinical-utility reasons despite
    # low absorption." That is a documented exception to the absorption-only
    # honesty_rule; whether to apply the rule (→13) is a USER policy decision,
    # not a unilateral edit. Alias cleanup (broad ubiquinol → generic) kept.
    ("inositol", "d-chiro-inositol", 10),           # absorption class-equiv to myo-inositol
    # NOTE: chromium chelidamate arginate left at 7 — pinned by Dr Pham Section C
    # clinician sign-off (test_b35_dr_pham_signoff_integrity.py). ChatGPT's
    # "downgrade to 6" was low-confidence and conflicts with that adjudication.
]


@pytest.mark.parametrize("parent,form,expected", SCORE_TARGETS)
def test_bio_score_corrected(iqm, parent, form, expected):
    assert _form(iqm, parent, form)["bio_score"] == expected


@pytest.mark.parametrize("parent,form,_", SCORE_TARGETS)
def test_score_invariant(iqm, parent, form, _):
    f = _form(iqm, parent, form)
    assert f["score"] == min(18, f["bio_score"] + (3 if f.get("natural") else 0))


# ── 2. natural-bonus misapplied to purified inositols ─────────────────────────
def test_purified_inositols_not_natural(iqm):
    for form in ["myo-inositol", "d-chiro-inositol"]:
        f = _form(iqm, "inositol", form)
        assert f["natural"] is False, f"{form} purified compound, not a natural-source matrix"
        assert f["score"] == f["bio_score"]


# ── 3. marketing / wrong-entity aliases removed ───────────────────────────────
def test_iodine_marketing_removed(iqm):
    al = _al(iqm, "iodine", "molecular iodine")
    for a in ["nascent iodine", "atomic iodine", "detoxified iodine", "transformative nano iodine"]:
        assert a not in al


def test_spm_downstream_products_off_17hdha(iqm):
    al = _al(iqm, "omega_3", "17-hydroxy-docosahexaenoic acid (17-HDHA)")
    for a in ["resolvins", "protectins", "specialized pro-resolving mediators"]:
        assert a not in al  # downstream product classes, not 17-HDHA


def test_natural_boron_off_fructoborate(iqm):
    assert "natural boron" not in _al(iqm, "boron", "calcium fructoborate")


def test_pinitol_off_dci(iqm):
    assert "d-pinitol" not in _al(iqm, "inositol", "d-chiro-inositol")  # CID 164619, distinct precursor


def test_ammonium_molybdate_off_sodium(iqm):
    assert "ammonium molybdate" not in _al(iqm, "molybdenum", "sodium molybdate")


def test_mytosterone_blend_off_saw_palmetto(iqm):
    al = _al(iqm, "saw_palmetto", "saw palmetto (unspecified)")
    assert not any("mytosterone" in a for a in al)


def test_generic_coq10_off_ubiquinone_standard(iqm):
    al = _al(iqm, "coq10", "ubiquinone standard")
    for a in ["coenzyme q10", "coq10", "coq-10"]:
        assert a not in al  # generic -> resolves via parent to coq10 (unspecified)


# ── 4. alias re-routing ───────────────────────────────────────────────────────
def test_generic_chelate_copper_to_aac(iqm):
    bis = _al(iqm, "copper", "copper bisglycinate")
    aac = _al(iqm, "copper", "copper amino acid chelate")
    for a in ["chelated copper", "albion copper", "traacs copper"]:
        assert a not in bis and a in aac


def test_broad_ubiquinol_to_generic(iqm):
    cf = _al(iqm, "coq10", "ubiquinol crystal-free")
    ub = _al(iqm, "coq10", "ubiquinol")
    for a in ["active coq10", "reduced coq10", "coqh2", "ubiquinol qh"]:
        assert a not in cf and a in ub


# ── 5. absorption string honest ───────────────────────────────────────────────
def test_copper_bisglycinate_absorption_honest(iqm):
    assert "75" not in _form(iqm, "copper", "copper bisglycinate")["absorption"]
