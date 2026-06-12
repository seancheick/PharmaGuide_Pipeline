"""Regression contract for the 2026-06 batch-7 IQM audit (taurine/ergothioneine/
l_carnitine/tmg_betaine/l_glutamine).

Verified: L-carnitine oral F low 14-18% + ALCAR superiority is delivery/CNS not
proven absorption (Rebouche 2004 PMID 15591001); betaine ~complete (Schwab 2006
PMID 16365055); Ala-Gln genuine ~2x glutamine AUC (Harris 2012 PMID 22575040,
CID 123935); taurine = 2-aminoethanesulfonic acid (CID 1123); glutamate (CID
33032) != glutamine (CID 5961). No sign-off forms in this batch.
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


# ── 1. ALCAR: BBB/delivery premium off (strict absorption, per the CoQ10 decision) ─
def test_alcar_bio_score(iqm):
    # ALCAR -> 10 (= tartrate/PLC ester tier): "absorbed without hydrolysis" edge
    # over base, but NOT a proven oral-F advantage; BBB positioning is not absorption.
    f = _form(iqm, "l_carnitine", "acetyl-l-carnitine (alcar)")
    assert f["bio_score"] == 10
    assert f["score"] == min(18, f["bio_score"] + (3 if f.get("natural") else 0))


# ── 2. marketing / typo / combo alias cleanup ────────────────────────────────
def test_taurine_marketing_removed_keep_liposome(iqm):
    al = _al(iqm, "taurine", "liposomal taurine")
    for a in ["nano taurine", "encapsulated taurine", "advanced delivery taurine"]:
        assert a not in al
    assert "liposome-encapsulated taurine" in al  # exact liposomal form alias kept


def test_ergothioneine_marketing_removed(iqm):
    al = _al(iqm, "ergothioneine", "l-ergothioneine")
    for a in ["longevity vitamin", "mitochondrial antioxidant", "cellular protector", "thiol antioxidant"]:
        assert a not in al


def test_brain_carnitine_off_alcar(iqm):
    assert "brain carnitine" not in _al(iqm, "l_carnitine", "acetyl-l-carnitine (alcar)")


def test_tmg_typo_alias_removed(iqm):
    assert "trimethylglycerine hydrochloride" not in {a.lower() for a in iqm["tmg_betaine"].get("aliases", [])}


def test_glutamate_combos_off_free_glutamine(iqm):
    al = _al(iqm, "l_glutamine", "l-glutamine powder")
    for a in ["glutamine & glutamic acid", "l-glutamine & glutamic acid",
              "glutamic acid and glutamine", "glutamic acid & glutamine"]:
        assert a not in al  # glutamate CID 33032 != glutamine CID 5961


def test_pepform_off_free_glutamine(iqm):
    al = _al(iqm, "l_glutamine", "l-glutamine powder")
    for a in ["pepform glutamine peptides", "pepform glutamine"]:
        assert a not in al  # peptide-bound, not free-form crystalline L-glutamine


def test_generic_peptides_off_alanyl_glutamine(iqm):
    assert "glutamine peptides" not in _al(iqm, "l_glutamine", "l-alanyl-l-glutamine")
