"""Regression contract for the 2026-06 batch-9 IQM audit (l_glycine/l_alanine/
l_histidine/l_serine/l_glutamic_acid + the glutamate duplicate).

The fix: the duplicate `glutamate` parent shared all of l_glutamic_acid's labels
(glutamate / l-glutamate / MSG / monosodium glutamate) but carried contradictory
metadata (val 0.85 + natural=true vs the verified l_glutamic_acid val 0.1 +
natural=false). Both already scored bio=6; aligning glutamate's val/natural makes
the shared labels score identically regardless of which parent matches. Glutamic
acid/glutamate is poorly systemically available (splanchnic extraction); MSG (the
dominant glutamate supplement form) is synthetic, not a natural-source matrix.

The full deprecate/merge of `glutamate` into `l_glutamic_acid` is architecture,
surfaced to the user. Other findings affirm current scores (l_alanine 9, l_serine
10) or defer (salt/D-serine/copper-histidinate forms, glycine achiral rename).
"""
import json
import os

import pytest

IQM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json")


@pytest.fixture(scope="module")
def iqm():
    with open(IQM_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def test_glutamate_aligned_to_glutamic_acid(iqm):
    g = iqm["glutamate"]["forms"]["l-glutamate"]
    assert g["natural"] is False                      # MSG/glutamate is synthetic, not natural matrix
    assert g["absorption_structured"]["value"] == 0.1  # splanchnic extraction (= l_glutamic_acid)
    assert g["score"] == min(18, g["bio_score"])       # natural bonus removed


def test_glutamate_no_longer_contradicts_glutamic_acid(iqm):
    g = iqm["glutamate"]["forms"]["l-glutamate"]
    ga = iqm["l_glutamic_acid"]["forms"]["l-glutamic acid standard"]
    # shared labels (glutamate/MSG) must score identically whichever parent wins
    assert g["bio_score"] == ga["bio_score"]
    assert g["natural"] == ga["natural"]
    assert g["absorption_structured"]["value"] == ga["absorption_structured"]["value"]
