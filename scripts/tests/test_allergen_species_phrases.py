"""Fish species and krill on a label name the allergen source.

2026-10-19 corpus measurement: rows such as "purified Arctic Cod Liver Oil"
(28705), Gelatin with forms Cod/Cusk/Flounder/Haddock/Hake/Pollock/Sole (8719,
FDA allergen Q&A Ed. 5 D.4's own example), Docosahexaenoic Acid with form Tuna
(56163), Shark Cartilage and Krill Oil, and statements such as "Contains:
Sardines, anchovies, soy" or "CONTAINS: Crustaceans (Krill).", shipped no fish
or crustacean flag. FDA requires the species, not the word "fish", on labels
(Q&A C.5/C.6), and the species names are deliberately not aliases so the
cleaner keeps IQM identity (cod_liver_oil, krill_oil). They are now
allergens.json match_rules.phrase_match_terms: matched only as whole words in
label text, never as identity aliases.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _hits(enricher, name="Vitamin C", forms=(), statements=()):
    product = {
        "id": "99990", "fullName": "Test",
        "statements": [{"type": "Precautions", "notes": s} for s in statements],
        "activeIngredients": [{"name": name, "forms": [{"name": f} for f in forms]}],
        "inactiveIngredients": [],
    }
    return {h["allergen_id"]: h for h in enricher._collect_contaminant_data(product)["allergens"]["allergens"]}


@pytest.mark.parametrize("name,forms,expected", [
    ("purified Arctic Cod Liver Oil", (), "ALLERGEN_FISH"),
    ("Gelatin", ("Cod", "Cusk", "Flounder", "Haddock", "Hake", "Pollock", "Sole"), "ALLERGEN_FISH"),
    ("Docosahexaenoic Acid", ("Tuna",), "ALLERGEN_FISH"),
    ("Shark Cartilage", (), "ALLERGEN_FISH"),
    ("Krill Oil", (), "ALLERGEN_CRUSTACEANS"),
    ("Antarctic Krill (Euphausia superba) Oil", (), "ALLERGEN_CRUSTACEANS"),
])
def test_species_row_names_the_allergen(enricher, name, forms, expected):
    assert expected in _hits(enricher, name, forms)


def test_species_form_is_named_in_the_evidence(enricher):
    hit = _hits(enricher, "Docosahexaenoic Acid", ("Tuna",))["ALLERGEN_FISH"]
    assert hit["evidence"] == "Ingredient: Docosahexaenoic Acid (from Tuna)"


def test_highly_refined_marine_oil_keeps_the_d9_exemption(enricher):
    # 328645: FDA Q&A D.9 exempts highly refined oils from allergen labeling.
    assert "ALLERGEN_FISH" not in _hits(
        enricher, "Highly Refined Marine Oil Concentrate", ("Anchovy", "Herring", "Mackerel", "Sardine"),
    )


@pytest.mark.parametrize("statement,expected", [
    ("Contains: Sardines, anchovies, soy", {"ALLERGEN_FISH", "ALLERGEN_SOY"}),
    ("Contains anchovy, herring, mackerel and sardine.", {"ALLERGEN_FISH"}),
    ("CONTAINS: Crustaceans (Krill).", {"ALLERGEN_CRUSTACEANS"}),
])
def test_contains_statement_naming_a_species_flags_it(enricher, statement, expected):
    hits = _hits(enricher, statements=(statement,))
    assert expected <= set(hits)
    assert all(hits[a]["presence_type"] == "contains" for a in expected)


@pytest.mark.parametrize("name", ["Codonopsis Root", "Sardinian Myrtle", "Contains no fish"])
def test_species_words_need_a_whole_word_positive_mention(enricher, name):
    assert "ALLERGEN_FISH" not in _hits(enricher, name)


def test_species_terms_are_not_identity_aliases_in_the_cleaner():
    normalizer = EnhancedDSLDNormalizer()
    for name in ("Cod Liver Oil", "Krill Oil", "Tuna", "Sardines"):
        assert not normalizer._priority_based_classification(name, [])["allergen_info"]["is_allergen"]


@pytest.mark.parametrize("statement,absent", [
    # Prose that mentions "contains" mid-sentence is not a declaration.
    ("Krill oil contains astaxanthin, which is not seen in standard fish oil.", "ALLERGEN_FISH"),
    ("Barley actually contains more beta glucan than oats.", "ALLERGEN_OATS"),
    # Negated declarations (corpus 218073, 220125).
    ("Contains none of the following: artificial dyes, preservatives, dairy, lactose, milk, soy.", "ALLERGEN_MILK"),
    ("Contains none of the following: artificial dyes, preservatives, dairy, lactose, milk, soy.", "ALLERGEN_SOY"),
    ("What's more, Macros doesn't contains soy, dairy or whey protein ingredients.", "ALLERGEN_MILK"),
])
def test_prose_and_negated_statements_are_not_declarations(enricher, statement, absent):
    assert absent not in _hits(enricher, statements=(statement,))


@pytest.mark.parametrize("statement,expected", [
    ("may contain traces of eggs, crab, pelagic wild sardine, shrimp, peanuts and wheat.", "ALLERGEN_FISH"),
    ("Allergens: Contains herring, mackerel, menhaden, sardines and soy.", "ALLERGEN_FISH"),
])
def test_declaration_shaped_statements_name_species(enricher, statement, expected):
    assert expected in _hits(enricher, statements=(statement,))
