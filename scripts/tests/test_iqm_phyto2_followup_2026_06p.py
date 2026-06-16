"""Follow-up: new items from a re-pasted batch-12 block (batch 12 = 2c204925).
chlorella species labels are not powder/cell-wall status; "broken wall algae"
is too broad; ALA "bio-enhanced/active" are ambiguous (could be Na-R-lipoate);
"Thiotic Acid" is a typo of thioctic acid; HA short-chain/nano are broader than
oligosaccharide (<10 kDa) and belong on the low-MW form.
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


def test_chlorella_species_to_unspecified(iqm):
    pw = _al(iqm, "chlorella", "chlorella powder")
    un = _al(iqm, "chlorella", "chlorella (unspecified)")
    for a in ["chlorella vulgaris", "chlorella pyrenoidosa"]:
        assert a not in pw and a in un


def test_broken_wall_algae_removed(iqm):
    assert "broken wall algae" not in _al(iqm, "chlorella", "broken cell wall chlorella")


def test_ala_ambiguous_marketing_removed(iqm):
    al = _al(iqm, "alpha_lipoic_acid", "R-alpha-lipoic acid")
    assert "bio-enhanced ala" not in al and "active ala" not in al


def test_thiotic_typo_mapped_to_racemic_not_r_form(iqm):
    """"Thiotic Acid" is a real-label misspelling of thioctic acid (e.g. Pure
    Encapsulations products print it). It carries no chirality signal, so it
    must resolve to the conservative racemic form — NOT be deleted (that
    regressed a real product, see test_enrichment_regressions) and NOT be
    placed on the chiral-specific R-alpha-lipoic acid form."""
    assert "thiotic acid" in _al(iqm, "alpha_lipoic_acid", "racemic alpha-lipoic acid")
    assert "thiotic acid" not in _al(iqm, "alpha_lipoic_acid", "R-alpha-lipoic acid")


def test_ha_short_chain_to_lowmw(iqm):
    oligo = _al(iqm, "hyaluronic_acid", "oligosaccharide HA")
    lowmw = _al(iqm, "hyaluronic_acid", "low molecular weight HA")
    for a in ["short-chain ha", "nano ha"]:
        assert a not in oligo and a in lowmw
