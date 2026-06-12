"""Regression contract for the 2026-06 batch-8 IQM audit (l_arginine/l_lysine/
l_tyrosine/l_cysteine/l_proline).

Verified (PubChem): standalone AKG (CID 51) != AAKG (CID 11427178); D-tyrosine
(CID 71098) != racemic; lysine HCl (CID 69568) = base lysine cation (salt only);
L-cystine (CID 67678) != L-cysteine (CID 5862). Scores were affirmed correct by
the audit (AAKG<Nitrosigine, NALT<L-Tyr, hydroxyproline<L-Pro) — NO score changes
this batch; only mis-routing fixes that currently produce a WRONG score.

Deferred (need new form / would orphan / architecture): cystine, cysteine-HCl,
tyrosine-HCl, arginine-pyroglutamate splits; hydroxyproline/zinc-cysteinate
decouple; missing salt + collagen-peptide forms (DSLD verification).
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


# ── standalone AKG mis-routed to an arginine form -> route to the AKG parent ──
def test_standalone_akg_off_aakg(iqm):
    assert "a-ketoglutarate" not in _al(iqm, "l_arginine", "l-arginine akG")
    # the dedicated AKG parent (CID 51 compound) now recognizes it
    assert "a-ketoglutarate" in _al(iqm, "alpha_ketoglutarate", "alpha-ketoglutarate (unspecified)")


# ── racemic tyrosine wrongly scored as punitive pure D-tyrosine (bio=2) ───────
def test_racemic_off_d_tyrosine(iqm):
    assert "racemic tyrosine mix" not in _al(iqm, "l_tyrosine", "d-tyrosine")


# ── generic lysine labels don't prove the HCl salt -> route to base (parity) ──
def test_generic_lysine_to_base(iqm):
    hcl = _al(iqm, "l_lysine", "l-lysine hcl")
    base = _al(iqm, "l_lysine", "l-lysine base")
    for a in ["pure l-lysine", "lysine powder", "micronized lysine"]:
        assert a not in hcl and a in base
