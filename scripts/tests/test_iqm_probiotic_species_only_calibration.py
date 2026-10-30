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
        ("saccharomyces_boulardii", "saccharomyces boulardii (unspecified)", 11),
        ("streptococcus_salivarius", "streptococcus salivarius (unspecified)", 10),
        ("lactobacillus_reuteri", "lactobacillus reuteri (unspecified)", 10),
        ("lactobacillus_casei", "lactobacillus casei (unspecified)", 10),
        ("lactobacillus_paracasei", "lactobacillus paracasei (unspecified)", 10),
        ("lactobacillus_gasseri", "lactobacillus gasseri (unspecified)", 10),
        ("bifidobacterium_breve", "bifidobacterium breve (unspecified)", 10),
        ("bacillus_coagulans", "bacillus coagulans (unspecified)", 11),
        ("bacillus_subtilis", "bacillus subtilis (unspecified)", 10),
        ("bacillus_clausii", "bacillus clausii (unspecified)", 11),
    ]

    for parent, form_name, expected_bio in species_only:
        form = data[parent]["forms"][form_name]
        assert form["bio_score"] == expected_bio
        assert form["absorption_structured"]["value"] < 0.8


def test_only_evidence_backed_named_probiotic_strains_remain_premium() -> None:
    data = _iqm()
    named_strains = {
        ("saccharomyces_boulardii", "saccharomyces boulardii cncm i-745"): 15,
        ("streptococcus_salivarius", "streptococcus salivarius k12"): 14,
        ("lactobacillus_reuteri", "lactobacillus reuteri DSM 17938"): 14,
        ("bacillus_coagulans", "bacillus coagulans gbi-30"): 14,
        # A specific name alone is not evidence for the former premium score.
        ("bacillus_subtilis", "bacillus subtilis de111"): 11,
    }

    for (parent, form_name), expected_bio in named_strains.items():
        form = data[parent]["forms"][form_name]
        assert form["bio_score"] == expected_bio


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


SALIVARIUS_SPECIES_ALIASES = [
    # Zheng et al. 2020 (PMID 32293557) renamed the species; GSRS UNII
    # 7A4S6N2EG2 names it Ligilactobacillus salivarius. No strain code.
    "ligilactobacillus salivarius",
    "ligilactobacillus salivarius supplement",
    "lactobacillus salivarius strain",
    "lactobacillus salivarius strain supplement",
]


def test_salivarius_species_names_are_not_aliases_of_the_ha118_strain() -> None:
    forms = _iqm()["lactobacillus_salivarius"]["forms"]
    strain = {a.lower() for a in forms["lactobacillus salivarius ha-118"]["aliases"]}
    generic = {a.lower() for a in forms["generic lactobacillus salivarius"]["aliases"]}
    for alias in SALIVARIUS_SPECIES_ALIASES:
        assert alias not in strain
        assert alias in generic


def test_species_only_salivarius_label_selects_the_generic_form() -> None:
    from enrich_supplements_v3 import SupplementEnricherV3

    enricher = SupplementEnricherV3()

    def form_of(name: str) -> tuple:
        row = {"name": name, "raw_source_text": name, "standardName": "Lactobacillus Salivarius",
               "canonical_id": "lactobacillus_salivarius", "canonical_source_db": "ingredient_quality_map",
               "ingredientGroup": "Lactobacillus salivarius", "raw_source_path": "ingredientRows[0]",
               "quantity": 1, "unit": "Billion CFU", "forms": [], "source_section": "active",
               "cleaner_row_role": "active_scorable", "score_eligible_by_cleaner": True}
        product, issues = enricher.enrich_product({"id": "salivarius", "fullName": "t",
                                                   "activeIngredients": [row], "inactiveIngredients": []})
        assert product, issues
        iqd = product["ingredient_quality_data"]
        out = (iqd["ingredients"] + iqd.get("ingredients_skipped", []))[0]
        return out.get("form_id") or out.get("matched_form"), out.get("bio_score")

    for name in ("Ligilactobacillus salivarius", "Lactobacillus salivarius strain"):
        assert form_of(name) == ("generic lactobacillus salivarius", 6)
    # The named strain keeps its own form.
    assert form_of("Lactobacillus salivarius HA-118") == ("lactobacillus salivarius ha-118", 7)
