"""Regression contract for the 2026-06 batch-3 IQM audit (botanicals + actives).

Content-verified PK/identity (PMIDs 22429945 oral-ATP-not-bioavailable,
15333514 resveratrol, 22551330 saw palmetto, 9405716 whey/casein; PubChem
CID 3071 DIM vs 3712 I3C; NCCIH). Invariant: score == bio_score + 3*natural.
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


# ── 1. unspecified-form inversions (unknown form must sit BELOW disclosed) +
#       oral-ATP not bioavailable intact + saw-palmetto liposomal evidence-thin ──
SCORE_TARGETS = [
    ("atp", "atp disodium salt", 7),                                  # intact ATP not orally bioavailable
    ("atp", "atp (adenosine triphosphate) (unspecified)", 6),         # below disodium
    ("stinging_nettle", "stinging nettle (unspecified)", 9),          # below root 11 / leaf 10
    ("pygeum", "pygeum (unspecified)", 8),                            # below bark extract 11
    ("saw_palmetto", "liposomal saw palmetto", 8),                   # no extraction-outcome edge (NCCIH)
]


@pytest.mark.parametrize("parent,form,expected", SCORE_TARGETS)
def test_bio_score_corrected(iqm, parent, form, expected):
    assert _form(iqm, parent, form)["bio_score"] == expected


@pytest.mark.parametrize("parent,form,_", SCORE_TARGETS)
def test_score_invariant(iqm, parent, form, _):
    f = _form(iqm, parent, form)
    assert f["score"] == min(18, f["bio_score"] + (3 if f.get("natural") else 0))


# ── 2. natural-bonus misapplied (purified salt / unknown source) ──────────────
def test_atp_disodium_not_natural(iqm):
    f = _form(iqm, "atp", "atp disodium salt")
    assert f["natural"] is False and f["score"] == f["bio_score"]


def test_pc_unspecified_not_natural(iqm):
    f = _form(iqm, "phosphatidylcholine", "phosphatidylcholine (unspecified)")
    assert f["natural"] is False and f["score"] == f["bio_score"]


# ── 3. marketing aliases removed ──────────────────────────────────────────────
# NOTE: black_cherry "sweet cherry"/"prunus avium" aliases were NOT removed.
# The black_cherry entry is deliberately Prunus avium (GSRS UNII A77056YJ4K,
# UMLS C5551209 — see test_iqm_black_cherry_entry.py). ChatGPT's "black cherry =
# P. serotina" is the botanical tree, not this supplement entry. The naming
# question is surfaced to the user pending GSRS species verification.
def test_marketing_aliases_removed(iqm):
    atp = _al(iqm, "atp", "atp disodium salt")
    assert "cellular energy" not in atp and "energy currency" not in atp
    saw = _al(iqm, "saw_palmetto", "liposterolic extract (85–95% fatty acids)")
    for a in ["herbal prostate formula", "prostate health extract", "lauric acid saw palmetto"]:
        assert a not in saw
    lyz = _al(iqm, "lysozyme", "lysozyme enzyme")
    assert "antimicrobial enzyme" not in lyz and "immune enzyme" not in lyz


# ── 4. generic/source aliases re-routed to the conservative form ──────────────
def test_generic_atp_to_unspecified(iqm):
    dis = _al(iqm, "atp", "atp disodium salt")
    uns = _al(iqm, "atp", "atp (adenosine triphosphate) (unspecified)")
    for a in ["atp", "adenosine triphosphate", "atp supplement"]:
        assert a not in dis and a in uns


def test_huzhang_source_off_trans_resveratrol(iqm):
    trans = _al(iqm, "resveratrol", "trans-resveratrol")
    uns = _al(iqm, "resveratrol", "resveratrol (unspecified)")
    for a in ["hu zhang", "reynoutria japonica root extract"]:
        assert a not in trans and a in uns


def test_generic_pc_to_unspecified(iqm):
    soy = _al(iqm, "phosphatidylcholine", "soy phosphatidylcholine")
    uns = _al(iqm, "phosphatidylcholine", "phosphatidylcholine (unspecified)")
    for a in ["phosphatidylcholine", "phosphatidylcholine complex", "phosphatidyl choline complex"]:
        assert a not in soy and a in uns


def test_generic_nettle_to_unspecified(iqm):
    root = _al(iqm, "stinging_nettle", "stinging nettle root extract")
    uns = _al(iqm, "stinging_nettle", "stinging nettle (unspecified)")
    for a in ["urtica dioica extract", "nettles", "nettle extract 10:1"]:
        assert a not in root and a in uns


def test_milk_caseinate_to_unspecified(iqm):
    assert "milk caseinate" not in _al(iqm, "casein", "calcium caseinate")
    assert "milk caseinate" in _al(iqm, "casein", "casein (unspecified)")


def test_generic_vanadyl_to_unspecified(iqm):
    voso4 = _al(iqm, "vanadyl_sulfate", "vanadyl sulfate (VOSO4)")
    uns = _al(iqm, "vanadyl_sulfate", "vanadyl sulfate (unspecified)")
    for a in ["vanadyl", "vanadyl supplement"]:
        assert a not in voso4 and a in uns


# ── 5. absorption display strings corrected ───────────────────────────────────
def test_absorption_strings_honest(iqm):
    assert "40-60%" not in _form(iqm, "atp", "atp disodium salt")["absorption"]
    assert not _form(iqm, "vanadyl_sulfate", "bis(maltolato)oxovanadium (BMOV)")["absorption"].lower().startswith("high")
    assert not _form(iqm, "black_cherry", "black cherry concentrate")["absorption"].lower().startswith("moderate")


# ── 6. casein parent_id (backwards, documentary-only) removed ─────────────────
def test_casein_parent_id_removed(iqm):
    assert (iqm["casein"].get("match_rules") or {}).get("parent_id") is None
