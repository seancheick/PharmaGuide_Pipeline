"""Regression contract for the 2026-06 batch-12 IQM audit (chlorella/
hyaluronic_acid/alpha_carotene/alpha_lipoic_acid/msm).

Identity verified (PubChem): alpha-carotene (CID 6419725) != beta-carotene
(CID 5280489), half provitamin-A (RAE 24 vs 12); MSM = dimethyl sulfone
(CID 6213), "organic sulfur" non-specific; R-ALA (CID 6112) vs racemic (CID 864);
HA MW classes distinct; chlorella cell-wall disruption is the absorption
determinant (PMID 39610880). No sign-off forms; bio_score contract already clean.
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


# ── flag + display-value consistency ─────────────────────────────────────────
def test_alpha_carotene_not_natural(iqm):
    f = iqm["alpha_carotene"]["forms"]["alpha-carotene (unspecified)"]
    assert f["natural"] is False                  # purified, no declared source
    assert f["score"] == min(18, f["bio_score"])


def test_msm_unspecified_value_aligned(iqm):
    # MSM = single compound (dimethyl sulfone); unspecified must match exact MSM
    ex = iqm["msm"]["forms"]["MSM (methylsulfonylmethane)"]
    un = iqm["msm"]["forms"]["msm (methylsulfonylmethane) (unspecified)"]
    assert ex["bio_score"] == un["bio_score"]
    assert un["absorption_structured"]["value"] == ex["absorption_structured"]["value"]


# ── alias cleanup ────────────────────────────────────────────────────────────
def test_chlorella_extract_protein_off_powder(iqm):
    al = _al(iqm, "chlorella", "chlorella powder")
    for a in ["chlorella extract powder", "chlorella protein concentrate", "chlorella protein powder"]:
        assert a not in al


def test_chlorella_marketing_off_broken_cell(iqm):
    al = _al(iqm, "chlorella", "broken cell wall chlorella")
    for a in ["processed chlorella", "bioavailable chlorella", "high-absorption chlorella"]:
        assert a not in al


def test_fermented_green_algae_off_chlorella(iqm):
    assert "fermented green algae" not in _al(iqm, "chlorella", "fermented chlorella")


def test_generic_lowmw_to_lowmw_form(iqm):
    oligo = _al(iqm, "hyaluronic_acid", "oligosaccharide HA")
    lowmw = _al(iqm, "hyaluronic_acid", "low molecular weight HA")
    assert "low mw hyaluronic acid" not in oligo and "low mw hyaluronic acid" in lowmw
    assert "ultra-low mw ha" in oligo  # oligo-specific ULMW labels kept


def test_ha_liposomal_marketing_removed(iqm):
    al = _al(iqm, "hyaluronic_acid", "liposomal HA")
    for a in ["encapsulated ha", "advanced delivery ha", "high-absorption ha"]:
        assert a not in al


def test_ala_generic_to_unspecified(iqm):
    rac = _al(iqm, "alpha_lipoic_acid", "racemic alpha-lipoic acid")
    uns = _al(iqm, "alpha_lipoic_acid", "alpha lipoic acid (unspecified)")
    for a in ["alpha-lipoic acid", "ala", "thioctic acid"]:
        assert a not in rac and a in uns
    for a in ["natural lipoic acid", "natural ala"]:
        assert a not in rac  # racemic is synthetic; natural-source labels removed


def test_ala_liposomal_marketing_removed(iqm):
    al = _al(iqm, "alpha_lipoic_acid", "liposomal alpha-lipoic acid")
    for a in ["nano ala", "encapsulated ala", "advanced delivery ala", "high-absorption ala"]:
        assert a not in al


def test_organic_sulfur_off_exact_msm(iqm):
    al = _al(iqm, "msm", "MSM (methylsulfonylmethane)")
    for a in ["organic sulfur", "msm sulfur", "sulfur msm"]:
        assert a not in al
