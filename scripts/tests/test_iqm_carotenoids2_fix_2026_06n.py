"""Regression contract: two genuinely-new findings from a re-pasted batch-11 block
(batch 11 itself already committed, f7ad79cd).

1. "lutein 2020" / "lutein 2020 marigold flower extract" = Lutemax-2020 free-lutein
   brand (the free-lutein form already carries Lutemax 2020) -> route to free-lutein,
   not unspecified.
2. stabilized sulforaphane is a pre-formed/cyclodextrin-stabilized delivery form
   (bypasses glucoraphanin conversion), NOT a natural whole-food matrix -> natural=false.
"""
import json
import os

import pytest

IQM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json")
FREE_LUTEIN = "free lutein (floraglo / lutemax, marigold)"


@pytest.fixture(scope="module")
def iqm():
    with open(IQM_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _al(iqm, p, f):
    return {a.lower() for a in iqm[p]["forms"][f].get("aliases", [])}


def test_lutemax_2020_on_free_lutein(iqm):
    uns = _al(iqm, "lutein", "lutein (unspecified)")
    free = _al(iqm, "lutein", FREE_LUTEIN)
    for a in ["lutein 2020", "lutein 2020 marigold flower extract"]:
        assert a not in uns and a in free


def test_stabilized_sulforaphane_not_natural(iqm):
    f = iqm["sulforaphane"]["forms"]["stabilized sulforaphane"]
    assert f["natural"] is False
    assert f["score"] == min(18, f["bio_score"])
