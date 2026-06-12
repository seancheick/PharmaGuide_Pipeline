"""Regression contract for the 2026-06 batch-6 IQM audit (probiotics/prebiotics/
choline/phosphatidylserine/phosphatidylinositol).

Verified: ISAPP — strain count is not a quality axis (Hill 2014 PMID 24912386),
prebiotics are local/selective (Gibson 2017 PMID 28611480); ODS — no comparative
choline-form bioavailability data; liposomal-PS/Actiserine superiority rests on a
single conflicted industry PK study. Invariant: score == bio + 3*natural.

Score changes only on NON-signed-off forms (probiotics-unspecified and pectin
sign-offs untouched). bovine-PS prion safety, choline category, HMO/PI natural
flags, S. thermophilus routing, and architecture merges are surfaced, not changed.
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


# ── 1. unspecified inversions + count/enhanced-form premiums removed ──────────
SCORE_TARGETS = [
    ("prebiotics", "prebiotics (unspecified)", 9),            # below disclosed FOS/GOS/HMO/XOS
    ("probiotics", "multi-strain blend (10+ strains)", 11),    # strain count != quality (ISAPP)
    ("choline", "choline citrate", 10),                        # = bitartrate; ODS no form difference
    ("choline", "choline chloride", 10),
    ("phosphatidylserine", "Actiserine (enhanced PS blend)", 10),     # 1 conflicted study, val 0.3
    ("phosphatidylserine", "liposomal phosphatidylserine", 12),       # no proven advantage = source tier
    ("phosphatidylserine", "phosphatidylserine (unspecified)", 10),   # below disclosed source forms
]


@pytest.mark.parametrize("parent,form,expected", SCORE_TARGETS)
def test_bio_score_corrected(iqm, parent, form, expected):
    assert _form(iqm, parent, form)["bio_score"] == expected


@pytest.mark.parametrize("parent,form,_", SCORE_TARGETS)
def test_score_invariant(iqm, parent, form, _):
    f = _form(iqm, parent, form)
    assert f["score"] == min(18, f["bio_score"] + (3 if f.get("natural") else 0))


# ── 2. concept/blend/marketing alias cleanup ─────────────────────────────────
def test_synbiotic_off_freeze_dried(iqm):
    al = _al(iqm, "probiotics", "freeze-dried with prebiotics")
    assert "synbiotics" not in al and "symbiotic formulation" not in al


def test_exact_strains_off_probiotic_unspecified(iqm):
    al = _al(iqm, "probiotics", "probiotics (unspecified)")
    assert "lactococcus lactis strain plasma" not in al
    assert not any("la-5" in a and "bb-12" in a for a in al)


def test_synbiotic_off_mixed_prebiotic(iqm):
    assert "synbiotic blend" not in _al(iqm, "prebiotics", "mixed prebiotic blend")


def test_brain_choline_off_alphagpc(iqm):
    assert "brain choline" not in _al(iqm, "choline", "alpha-GPC")


def test_broad_soy_off_soy_ps(iqm):
    assert "soy-derived" not in _al(iqm, "phosphatidylserine", "soy-derived phosphatidylserine")


def test_sharp_ps_off_unspecified(iqm):
    al = _al(iqm, "phosphatidylserine", "phosphatidylserine (unspecified)")
    assert not any("sharp" in a for a in al)  # consolidated to its verified source form


def test_phosphoinositides_off_pi(iqm):
    assert "phosphoinositides" not in _al(iqm, "phosphatidylinositol", "phosphatidylinositol standard")
