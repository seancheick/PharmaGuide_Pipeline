"""Regression contract for the 2026-06 batch-5 IQM audit (PQQ/curcumin/quercetin/
glutathione/GPx). PK/identity content-verified (curcumin conjugate-dominance
Vareed 2008 PMID 18559556; quercetin poor F Hollman 1995 PMID 7491892; S-acetyl-
GSH 80-90% claim REFUTED, no human PK; GGC CID 123938 != GSH CID 124886; GSSG
CID 65359; GPx selenoenzyme family PMID 23201771). Invariant: score == bio + 3*natural.

Score changes are limited to NON-signed-off forms. Dr Pham sign-off forms
(LifePQQ, NovaSol/CurcuWin/Meriva/Theracurmin, liposomal glutathione) are NOT
touched; the curcumin hydrocurc/bcm-95 ranking is surfaced to the user, not reshuffled.
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


# ── 1. score corrections (non-signed-off, verified) ───────────────────────────
SCORE_TARGETS = [
    ("quercetin", "quercetin phytosome", 10),       # class-poor (val 0.1) below better-absorbed EMIQ
    ("glutathione", "s-acetyl glutathione", 9),      # 80-90% claim refuted (no human PK)
]


@pytest.mark.parametrize("parent,form,expected", SCORE_TARGETS)
def test_bio_score_corrected(iqm, parent, form, expected):
    assert _form(iqm, parent, form)["bio_score"] == expected


# ── 2. natural-bonus misapplied to purified/generic compounds + an enzyme ─────
def test_purified_not_natural(iqm):
    for p, f in [("quercetin", "quercetin dihydrate"), ("quercetin", "quercetin (unspecified)"),
                 ("glutathione_peroxidase", "glutathione peroxidase enzyme")]:
        x = _form(iqm, p, f)
        assert x["natural"] is False, f"{p}::{f}"
        assert x["score"] == min(18, x["bio_score"])


# ── 3. distinct-compound aliases removed (verified different CIDs) ─────────────
def test_ggc_precursor_off_glutathione(iqm):
    al = _al(iqm, "glutathione", "standard glutathione")
    assert "gamma-glutamylcysteine" not in al and "gamma-glutamylcysteines" not in al  # CID 123938 != GSH


def test_gssg_off_reduced_glutathione(iqm):
    al = _al(iqm, "glutathione", "glutathione (unspecified)")
    for a in ["oxidized glutathione", "gssg", "glutathione disulfide"]:
        assert a not in al  # CID 65359, oxidized dimer


def test_gsh_vitc_combos_off_standard(iqm):
    al = _al(iqm, "glutathione", "standard glutathione")
    for a in ["reduced glutathione with vitamin c", "gsh with vitamin c", "glutathione plus vitamin c"]:
        assert a not in al


def test_free_acid_pqq_off_disodium(iqm):
    dis = _al(iqm, "pqq", "disodium PQQ")
    uns = _al(iqm, "pqq", "pqq (pyrroloquinoline quinone) (unspecified)")
    for a in ["pqq acid", "free acid pqq"]:
        assert a not in dis and a in uns  # CID 1024 free acid != CID 91864988 disodium


def test_pqq_blend_delivery_aliases_removed(iqm):
    al = _al(iqm, "pqq", "pqq (pyrroloquinoline quinone) (unspecified)")
    for a in ["pqq with coq10", "pqq coq10 complex", "pqq + coq10", "liposomal pqq", "nano pqq"]:
        assert a not in al


def test_generic_glycoside_off_emiq(iqm):
    assert "quercetin glycoside" not in _al(iqm, "quercetin", "isoquercetin (EMIQ)")


def test_anhydrous_off_dihydrate(iqm):
    assert "quercetin anhydrous" not in _al(iqm, "quercetin", "quercetin dihydrate")


def test_dihydrate_off_unspecified(iqm):
    assert "quercetin dihydrate" not in _al(iqm, "quercetin", "quercetin (unspecified)")


def test_gpx_marketing_aliases_removed(iqm):
    al = _al(iqm, "glutathione_peroxidase", "glutathione peroxidase enzyme")
    for a in ["cellular peroxidase", "antioxidant enzyme gpx", "gpx antioxidant enzyme"]:
        assert a not in al


# ── 4. GPx is NOT a form of glutathione (it's a selenoenzyme that USES it) ────
def test_gpx_not_form_of_glutathione(iqm):
    # The false "form_of -> glutathione" relationship was removed. (A typed
    # "uses_substrate" link would require adding to the relationship vocabulary
    # enum — left as a user schema decision; the substrate fact is in the notes.)
    rels = iqm["glutathione_peroxidase"].get("relationships", [])
    assert not [r for r in rels if r.get("target_id") == "glutathione" and r.get("type") == "form_of"]
