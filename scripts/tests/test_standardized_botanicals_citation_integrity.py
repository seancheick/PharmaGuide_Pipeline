"""Standardized-botanical sources cite real papers about the entry they support.

A PMID that does not exist is a fabricated identifier. Receipts:
scripts/audits/pending_items_20260926/research.md.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
ENTRIES = {
    entry["id"]: entry
    for entry in json.loads((DATA / "standardized_botanicals.json").read_text())["standardized_botanicals"]
}


def test_ginger_cites_the_marx_2017_review_not_a_nonexistent_pmid():
    """PMID 28200047 does not exist in PubMed. The source line named Marx et al.
    2017; that paper is PMID 25848702 (Crit Rev Food Sci Nutr), a narrative
    review of ginger's mechanism in chemotherapy-induced nausea, not a
    systematic review."""
    sources = " ".join(ENTRIES["ginger_extract"]["sources"])
    assert "28200047" not in sources
    assert "PMID 25848702" in sources
    assert "systematic review" not in sources


def test_slendesta_cites_a_potato_pi2_satiety_trial_not_a_nonexistent_pmid():
    """PMID 22647284 does not exist in PubMed. PMID 28485429 (Zhu 2017, Food
    Funct) is a randomized trial of potato extract standardized to 15 or 30 mg
    proteinase inhibitor II: lower hunger, higher fullness, higher CCK."""
    sources = ENTRIES["slendesta"]["sources"]
    assert not any("22647284" in s for s in sources)
    assert "https://pubmed.ncbi.nlm.nih.gov/28485429/" in sources


import pytest


@pytest.mark.parametrize('key,index,pmid', [
    ('neurofactor', 0, '24013626'), ('life_s_dha', 0, '18689548'),
    ('sea_buckthorn_seed_oil', 1, '18689548'), ('lutemax_2020', 0, '28494836'),
    ('lutemax_2020', 1, '29144655'), ('microactive_melatonin', 0, '27535533'),
    ('nettle', 1, '15211420'), ('optiberry', 0, '15050362'),
    ('optiberry', 1, '16219800'), ('pacran', 1, '27013539'),
    ('pycnogenol', 0, '22260513'), ('sea_buckthorn', 0, '20429767'),
    ('sea_buckthorn', 1, '24787677'), ('sea_buckthorn_seed_oil', 0, '19883366'),
    ('sharp_ps_green', 0, '24345046'), ('thermosil', 0, '18046594'),
    ('turkey_tail', 0, '22972503'), ('turmipure_gold', 0, '31935893'),
    ('uniflex', 0, '19185917'),
])
def test_returned_rejected_preparation_sources_are_not_affirmative(key, index, pmid):
    source = ENTRIES[key]['sources'][index]
    assert pmid in source
    assert source.startswith('Rejected attribution')


def test_unresolved_preparation_awards_use_existing_hold():
    for key in ['floraglo', 'pycnogenol']:
        row = ENTRIES[key]
        assert row['bonus_eligible'] is False
        assert row['data_quality'] == 'requires_verification'
    assert 'not statistically significant' in ENTRIES['floraglo']['bonus_rationale']
    assert 'not Pycnogenol specification' in ENTRIES['pycnogenol']['bonus_rationale']
    assert 'in-vitro' in ENTRIES['nettle']['sources'][2]
