"""Regression contract for the 2026-06 batch-11 IQM audit (lutein/zeaxanthin/
sulforaphane/spermidine/spirulina).

Identity verified (PubChem): meso-zeaxanthin (CID 6442658) != zeaxanthin (CID
5280899); glucoraphanin (CID 9548634) != sulforaphane (CID 5350); spermidine
(CID 1102) is a polyamine; A. platensis != A. maxima; blue-green algae (incl.
toxin-bearing AFA, PMID 10499991) != spirulina.

Spirulina forms are Dr Pham signed off (scores untouched; only aliases cleaned).
Surfaced: spirulina-unspecified inversion (bio 11, signed off), A. maxima species
mismatch, spermidine wheat-germ natural split + category (polyamine -> other).
"""
import json
import os

import pytest

IQM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json")


@pytest.fixture(scope="module")
def iqm():
    with open(IQM_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _al(iqm, p, f):
    return {a.lower() for a in iqm[p]["forms"][f].get("aliases", [])}


# ── zeaxanthin unspecified: natural bonus misapplied (no declared source) ─────
def test_zeaxanthin_unspecified_not_natural(iqm):
    f = iqm["zeaxanthin"]["forms"]["zeaxanthin (unspecified)"]
    assert f["natural"] is False
    assert f["score"] == min(18, f["bio_score"])


# ── identity / class alias cleanup ───────────────────────────────────────────
def test_macularsynergy_off_lutein(iqm):
    al = _al(iqm, "lutein", "lutein (unspecified)")
    for a in ["macularsynergy complex", "macular synergy complex", "macularsynergy"]:
        assert a not in al


def test_generic_glucosinolate_moved_to_class(iqm):
    gr = _al(iqm, "sulforaphane", "glucoraphanin")
    assert "glucosinolate" not in gr                       # generic class != glucoraphanin
    assert "sulforaphane glucosinolate" in gr              # SGS = glucoraphanin synonym, kept
    assert "glucosinolate" in _al(iqm, "glucosinolates", "glucosinolates (unspecified)")


def test_myrosinase_enzyme_off_combo(iqm):
    assert "myrosinase" not in _al(iqm, "sulforaphane", "glucoraphanin + myrosinase")


def test_delivery_marketing_off_sulforaphane(iqm):
    al = _al(iqm, "sulforaphane", "sulforaphane (unspecified)")
    for a in ["liposomal sulforaphane", "nano sulforaphane", "encapsulated sulforaphane"]:
        assert a not in al


def test_blue_green_algae_off_spirulina_powder(iqm):
    al = _al(iqm, "spirulina", "spirulina powder")
    for a in ["blue-green algae", "green algae powder", "spirulina extract powder"]:
        assert a not in al


def test_marketing_off_organic_spirulina(iqm):
    al = _al(iqm, "spirulina", "organic spirulina")
    for a in ["clean spirulina", "natural spirulina", "eco-friendly spirulina", "green spirulina"]:
        assert a not in al
