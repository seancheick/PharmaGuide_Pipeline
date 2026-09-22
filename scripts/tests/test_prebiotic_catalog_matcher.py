"""One prebiotic vocabulary: the registry catalog drives enrichment and scoring alike."""
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from prebiotic_catalog import match_prebiotic, normalize_prebiotic_text, prebiotic_catalog, row_quantity_g

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "scripts/data/clinically_relevant_strains.json"
AMBIGUOUS_ALIASES = {"human milk oligosaccharide"}  # declared on both 2'-FL and LNnT on purpose


def test_catalog_is_the_registry_prebiotic_list():
    rows = json.loads(REGISTRY.read_text())["prebiotics"]["ingredients"]
    assert [name for name, _ in prebiotic_catalog()] == [r["standard_name"] for r in rows]
    assert len(rows) == 15  # Resistant Dextrin split from Resistant Starch (2026-09-22)


def test_every_catalog_name_and_alias_resolves_to_its_own_entry():
    rows = json.loads(REGISTRY.read_text())["prebiotics"]["ingredients"]
    for row in rows:
        for label in [row["standard_name"], *row["aliases"]]:
            match = match_prebiotic(label)
            assert match.present, label
            if normalize_prebiotic_text(label) in AMBIGUOUS_ALIASES:
                assert match.ambiguous and match.standard_name is None, label
            else:
                assert match.standard_name == row["standard_name"], label


def test_no_undeclared_duplicate_aliases_across_entries():
    seen = Counter(term for _, terms in prebiotic_catalog() for term in terms)
    assert {t for t, n in seen.items() if n > 1} == AMBIGUOUS_ALIASES


@pytest.mark.parametrize("label,expected", [
    ("Organic Acacia Fiber", "Acacia Fiber"),
    ("FOS (Fructooligosaccharides)", "Fructooligosaccharides"),
    ("Partially Hydrolyzed Guar Gum (Sunfiber)", "Partially Hydrolyzed Guar Gum"),
    ("XOS 95%", "Xylooligosaccharides"),
    ("Digestion Resistant Maltodextrin", "Resistant Dextrin"),
    ("Oat Beta-Glucan", "Beta-Glucan"),
    ("2'-FL", "2'-Fucosyllactose"),
    ("Raftiline HP", "Inulin"),
    ("Citrus Pectin", "Pectin"),
    ("Apple Pectin", "Pectin"),
])
def test_label_phrases_resolve_to_catalog_entries(label, expected):
    assert match_prebiotic(label).standard_name == expected


@pytest.mark.parametrize("label", ["Dietary Fiber", "Psyllium Husk Powder", "Pea Fiber", "Fiber blend", "Bacteriophage cocktail (PreforPro)", "Maltodextrin"])
def test_generic_fiber_and_non_prebiotics_never_match(label):
    assert not match_prebiotic(label).present


def test_shared_alias_is_present_but_never_resolved_to_one_entry():
    match = match_prebiotic("Human Milk Oligosaccharide 1 g")
    assert match.present and match.ambiguous and match.standard_name is None


def test_bare_prebiotic_label_is_present_with_unresolved_identity():
    match = match_prebiotic("Prebiotic Blend")
    assert match.present and match.standard_name is None and not match.ambiguous


@pytest.mark.parametrize("label", [
    "Pomegranate extract",
    "Pomegranate fruit extract",
    "Punica granatum extract",
])
def test_generic_pomegranate_extract_is_not_promoted_to_a_prebiotic(label):
    """Only the studied DS-01 polyphenol preparation has prebiotic identity."""
    assert not match_prebiotic(label).present


@pytest.mark.parametrize("label", [
    "Pomegranate Polyphenol Extract",
    "Indian pomegranate extract",
    "Indian pomegranate fruit MAPP",
    # DS-01's own label row (2026-09-16 app walkthrough: shipped
    # prebiotic_present=False, so "Prebiotic included" was hidden while the
    # score credited the prebiotic through the studied-formula brand token).
    "MAPP Microbiota-Accessible Polyphenolic Precursors",
])
def test_seed_pomegranate_preparation_retains_prebiotic_identity(label):
    assert match_prebiotic(label).standard_name == "Pomegranate Polyphenol Extract"


def test_row_quantity_g_units():
    assert row_quantity_g({"quantity": 3, "unit": "g"}) == 3
    assert row_quantity_g({"quantity": 500, "unit": "mg"}) == 0.5
    assert row_quantity_g({"quantity": 5, "unit": "billion CFU"}) is None
    assert row_quantity_g({"quantity": None}) is None


# ---- scorer: full credit for any catalog prebiotic at >= 3 g, not only the old regex subset
def _scorer_product(rows):
    from test_v4_probiotic_formulation_p21 import _product
    product = _product(prebiotic_present=True)
    product["ingredient_quality_data"]["ingredients_scorable"] = [
        {"name": "Lactobacillus rhamnosus", "canonical_id": "lacto", "mapped": True, "has_dose": True},
        *rows,
    ]
    return product


@pytest.mark.parametrize("name", [
    "Partially Hydrolyzed Guar Gum", "Resistant Starch", "Citrus Pectin", "Xylooligosaccharides",
    "Polydextrose", "Lactulose", "Oat Beta-Glucan", "2'-Fucosyllactose",
])
def test_scorer_gives_full_credit_to_every_catalog_prebiotic_at_three_grams(name):
    from scoring_v4.modules.probiotic_formulation import score_formulation
    product = _scorer_product([{"name": name, "canonical_id": "x", "mapped": True, "has_dose": True, "quantity": 3.0, "unit": "g"}])
    assert score_formulation(product)["components"]["prebiotic_complement"] == 1.0


def test_scorer_does_not_count_generic_fiber_grams_as_prebiotic_dose():
    from scoring_v4.modules.probiotic_formulation import score_formulation
    product = _scorer_product([
        {"name": "Inulin", "canonical_id": "inulin", "mapped": True, "has_dose": True, "quantity": 100, "unit": "mg"},
        {"name": "Psyllium Husk Fiber", "canonical_id": "psyllium", "mapped": True, "has_dose": True, "quantity": 5.0, "unit": "g"},
    ])
    assert score_formulation(product)["components"]["prebiotic_complement"] == 0.25


def test_scorer_prefers_the_enricher_dose_when_present():
    from scoring_v4.modules.probiotic_formulation import score_formulation
    product = _scorer_product([])
    product["probiotic_data"]["prebiotic_dose_g"] = 3.0
    assert score_formulation(product)["components"]["prebiotic_complement"] == 1.0


# ---- enricher: same matcher, and the dose now travels in probiotic_data
@pytest.fixture
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    return SupplementEnricherV3()


def _probiotic_product(extra_rows):
    strain = {"name": "Lactobacillus rhamnosus GG", "category": "probiotic", "quantity": 10, "unit": "billion CFU",
              "raw_source_path": "ingredientRows[0]", "ingredientGroup": "Lactobacillus rhamnosus GG"}
    return {"product_name": "Synbiotic", "activeIngredients": [strain, *extra_rows], "inactiveIngredients": []}


def test_enricher_reports_catalog_identity_and_dose(enricher):
    row = {"name": "Sunfiber (Partially Hydrolyzed Guar Gum)", "quantity": 3, "unit": "g", "raw_source_path": "ingredientRows[1]"}
    data = enricher._collect_probiotic_data(_probiotic_product([row]))
    assert data["prebiotic_present"] is True
    assert data["prebiotic_name"] == "Partially Hydrolyzed Guar Gum"
    assert data["prebiotic_dose_g"] == 3


def test_enricher_keeps_ambiguous_hmo_unresolved(enricher):
    row = {"name": "Human Milk Oligosaccharide", "quantity": 1, "unit": "g", "raw_source_path": "ingredientRows[1]"}
    data = enricher._collect_probiotic_data(_probiotic_product([row]))
    assert data["prebiotic_present"] is True
    assert data["prebiotic_name"] == "Human Milk Oligosaccharide"
    assert data["prebiotic_dose_g"] == 1


def test_enricher_ignores_generic_fiber_and_marketing_notes(enricher):
    rows = [
        {"name": "Psyllium Husk", "quantity": 5, "unit": "g", "raw_source_path": "ingredientRows[1]"},
        {"name": "Rice Flour", "notes": "a prebiotic-friendly formula", "raw_source_path": "ingredientRows[2]"},
    ]
    data = enricher._collect_probiotic_data(_probiotic_product(rows))
    assert data["prebiotic_present"] is False
    assert data["prebiotic_dose_g"] is None


def test_enricher_keeps_name_and_amount_on_the_same_row(enricher):
    rows = [{"name": "Inulin", "quantity": 100, "unit": "mg"},
            {"name": "Sunfiber", "quantity": 3, "unit": "g"}]
    data = enricher._collect_probiotic_data(_probiotic_product(rows))
    assert (data["prebiotic_name"], data["prebiotic_dose_g"]) == ("Partially Hydrolyzed Guar Gum", 3)


def test_mixed_blend_dose_is_not_an_ingredient_dose(enricher):
    row = {"name": "Digestive Blend (Inulin, Protease)", "quantity": 5, "unit": "g",
           "nestedIngredients": [{"name": "Inulin"}, {"name": "Protease"}]}
    data = enricher._collect_probiotic_data(_probiotic_product([row]))
    assert data["prebiotic_present"] is True
    assert data["prebiotic_dose_g"] is None


def test_named_ingredient_in_marketing_notes_does_not_own_the_row_mass(enricher):
    row = {"name": "Rice Flour", "quantity": 5, "unit": "g", "notes": "Combine with inulin for prebiotic support"}
    data = enricher._collect_probiotic_data(_probiotic_product([row]))
    assert data["prebiotic_present"] is False


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), -1])
def test_invalid_mass_is_not_a_disclosed_dose(amount):
    assert row_quantity_g({"quantity": amount, "unit": "g"}) is None
