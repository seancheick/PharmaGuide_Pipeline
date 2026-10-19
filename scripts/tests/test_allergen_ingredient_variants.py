"""Ingredient rows that name an allergen source are flagged, not only exact aliases.

2026-10-19 corpus measurement (scripts/audits/allergen_variant_matching_20261019/):
the enricher's ingredient-list allergen check matched only whole-name aliases, so
"Whey Protein Isolate", "Purified Deep Sea Fish Oil", "Soy Protein Isolate" or a
row whose form is "Fish Oil" shipped no allergen flag unless the label also had a
"Contains" statement. An alias is now matched as a whole-word phrase in the row
name or its forms. The canonical identity (standardName) is not evidence: algal
omega-3 rows carry the fish_oil identity. Reviewed different-organism phrases and
FDA-exempt highly refined oils are vetoed through each entry's
match_rules.negative_match_terms.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _allergen_ids(enricher, name, forms=(), standard_name=None, section="activeIngredients"):
    row = {"name": name, "forms": [{"name": f} for f in forms]}
    if standard_name:
        row["standardName"] = standard_name
    product = {"id": "99990", "fullName": "Test", "statements": [],
               "activeIngredients": [], "inactiveIngredients": []}
    product[section].append(row)
    found = enricher._collect_contaminant_data(product)["allergens"]["allergens"]
    return {a["allergen_id"] for a in found}


@pytest.mark.parametrize("name,forms,expected", [
    ("Whey Protein Isolate", (), "ALLERGEN_MILK"),
    ("Milk Dry Nonfat", (), "ALLERGEN_MILK"),
    ("L-Leucine", ("Calcium Caseinate",), "ALLERGEN_MILK"),
    ("Purified Deep Sea Fish Oil", (), "ALLERGEN_FISH"),
    ("Omega-3 Fatty Acids", ("Fish Oil",), "ALLERGEN_FISH"),
    ("Vitamin A", ("Fish Liver Oil",), "ALLERGEN_FISH"),
    ("Soy Protein Isolate", (), "ALLERGEN_SOY"),
    ("Soy Bean Isoflavones", (), "ALLERGEN_SOY"),
    ("Phosphatidylcholine", ("Soy Lecithin",), "ALLERGEN_SOY"),
    ("Sesame Seed Lignan Extract", (), "ALLERGEN_SESAME"),
    ("Macadamia Nut Oil", (), "ALLERGEN_TREE_NUTS"),
    ("Organic Barley", (), "ALLERGEN_BARLEY"),
    ("Diastase", ("Malt",), "ALLERGEN_BARLEY"),
    ("Glucosamine Sulfate", ("Shellfish",), "ALLERGEN_CRUSTACEANS"),
    ("Squid Oil", (), "ALLERGEN_MOLLUSCS"),
])
def test_row_naming_an_allergen_source_is_flagged(enricher, name, forms, expected):
    assert expected in _allergen_ids(enricher, name, forms)


@pytest.mark.parametrize("name,forms", [
    ("Milk Thistle Seed Extract", ()),
    ("Silymarin", ("Milk Thistle",)),
    ("Organic Coconut Milk", ()),
    ("Coconut Cream", ()),
    ("Dairy Digestive Enzymes", ()),
    ("BioCore Dairy", ()),
    ("Horse Chestnut Seed Extract", ()),
    ("Tropical Almond (Terminalia chebula)", ()),
    ("Almond Mushroom", ()),
    ("Gluten Enzyme Blend", ()),
    ("Mannitol", ("Wheat",)),
    ("Xylitol", ("Wheat",)),
    ("Mustard Greens", ()),
    ("Rye Flower Pollen Extract", ()),
    ("Graminex Flower Pollen Extract", ("Rye",)),
    ("Highly Refined Fish Oil", ()),
    ("Eggplant", ()),
])
def test_reviewed_non_allergen_phrases_are_not_flagged(enricher, name, forms):
    assert _allergen_ids(enricher, name, forms) == set()


def test_canonical_identity_alone_is_not_allergen_evidence(enricher):
    # Algal omega-3 rows carry the fish_oil identity; only the label text counts.
    assert _allergen_ids(
        enricher, "Omega-3 Fatty Acids", ("Algal Oil Concentrate",), standard_name="Fish Oil",
    ) == set()


def test_exact_alias_and_inactive_rows_still_flag(enricher):
    assert _allergen_ids(enricher, "Soy Lecithin", section="inactiveIngredients") == {"ALLERGEN_SOY"}
    assert _allergen_ids(enricher, "Fish Gelatin", section="inactiveIngredients") == {"ALLERGEN_FISH"}


def test_negative_terms_never_veto_an_entry_alias():
    import json
    from constants import ALLERGENS
    from identity.safety import negative_match_terms_veto

    for entry in json.loads(ALLERGENS.read_text(encoding="utf-8"))["allergens"]:
        terms = (entry.get("match_rules") or {}).get("negative_match_terms", [])
        for alias in [entry["standard_name"], *entry["aliases"]]:
            assert not negative_match_terms_veto([alias], terms), (entry["id"], alias)
        # The fish-oil note used to promise a cross-reference that never existed.
        assert "allergen cross-reference" not in entry.get("notes", "")
