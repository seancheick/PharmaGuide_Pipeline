"""IQM probiotic species-only calibration guard.

Species-only probiotic rows are useful survivability/identity signals, but they
must not score like exact clinical strains. v4 probiotic scoring gives separate
credit for named strain identity, CFU disclosure, and strain-specific evidence.
"""

from __future__ import annotations

import json
from pathlib import Path


IQM_PATH = Path(__file__).parent.parent / "data" / "ingredient_quality_map.json"


def _iqm() -> dict:
    with IQM_PATH.open() as f:
        return json.load(f)


def test_used_species_only_probiotic_forms_are_not_premium_strain_tier() -> None:
    data = _iqm()
    species_only = [
        ("saccharomyces_boulardii", "saccharomyces boulardii (unspecified)", 12),
        ("streptococcus_salivarius", "streptococcus salivarius (unspecified)", 10),
        ("lactobacillus_reuteri", "lactobacillus reuteri (unspecified)", 10),
        ("lactobacillus_casei", "lactobacillus casei (unspecified)", 10),
        ("lactobacillus_paracasei", "lactobacillus paracasei (unspecified)", 10),
        ("lactobacillus_gasseri", "lactobacillus gasseri (unspecified)", 10),
        ("bifidobacterium_breve", "bifidobacterium breve (unspecified)", 10),
        ("bacillus_coagulans", "bacillus coagulans (unspecified)", 12),
        ("bacillus_subtilis", "bacillus subtilis (unspecified)", 12),
        ("bacillus_clausii", "bacillus clausii (unspecified)", 12),
    ]

    for parent, form_name, expected_bio in species_only:
        form = data[parent]["forms"][form_name]
        assert form["bio_score"] == expected_bio
        assert form["score"] == min(18, expected_bio + 3)
        assert form["absorption_structured"]["value"] < 0.8


def test_named_probiotic_strains_can_remain_premium() -> None:
    data = _iqm()
    named_strains = [
        ("saccharomyces_boulardii", "saccharomyces boulardii cncm i-745"),
        ("streptococcus_salivarius", "streptococcus salivarius k12"),
        ("lactobacillus_reuteri", "lactobacillus reuteri DSM 17938"),
        ("bacillus_coagulans", "bacillus coagulans gbi-30"),
        ("bacillus_subtilis", "bacillus subtilis de111"),
    ]

    for parent, form_name in named_strains:
        form = data[parent]["forms"][form_name]
        assert form["bio_score"] >= 14


def test_exact_l_reuteri_dsm17938_aliases_do_not_live_on_unspecified_row() -> None:
    data = _iqm()
    unspecified_aliases = {
        a.lower()
        for a in data["lactobacillus_reuteri"]["forms"][
            "lactobacillus reuteri (unspecified)"
        ]["aliases"]
    }
    dsm_aliases = {
        a.lower()
        for a in data["lactobacillus_reuteri"]["forms"][
            "lactobacillus reuteri DSM 17938"
        ]["aliases"]
    }

    for alias in {"dsm 17938", "protectis", "biogaia"}:
        assert alias not in unspecified_aliases
        assert alias in dsm_aliases
