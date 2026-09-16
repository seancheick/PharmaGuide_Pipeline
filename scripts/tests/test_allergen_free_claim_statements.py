"""Free-from label statements reach the shipped compliance flags.

2026-09-16 silent-empty audit: is_soy_free shipped 0 for ~1,900 products and
is_dairy_free for ~270 whose labels say they are free of it. Two causes, both
in the claim-rules owner (data/cert_claim_rules.json +
SupplementEnricherV3._check_claim_with_validation):

1. The proximity check rejected a claim because of its own words: "no soy" and
   "No Dairy" contain the conflict token and only "soy-free"/"soy free" were
   exempt (243169 "Gluten free, no eggs, no soy."; 5821 "No Wheat, No Gluten,
   No Dairy, Yeast Free.").
2. List wording never matched: "No gluten, dairy, soy, peanuts or tree nuts"
   (297662).

The flags are shown to allergic users, so every positive case is paired with a
safety case that must stay not-free.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _product(*notes, inactive=()):
    return {
        "id": "free_from_statement",
        "fullName": "Daily Multivitamin",
        "statements": [
            {"type": "Formulation re: Does NOT Contain", "notes": note} for note in notes
        ],
        "activeIngredients": [],
        "inactiveIngredients": [{"name": name} for name in inactive],
        "targetGroups": [],
    }


@pytest.mark.parametrize("note, flag", [
    ("Gluten free, no eggs, no soy.", "soy_free"),
    ("No Wheat, No Gluten, No Dairy, Yeast Free.", "dairy_free"),
    ("No gluten, dairy, soy, peanuts or tree nuts", "soy_free"),
    ("No gluten, dairy, soy, peanuts or tree nuts", "dairy_free"),
    ("Made without gluten, dairy or soy.", "soy_free"),
])
def test_free_from_statement_sets_the_flag(enricher, note, flag):
    assert enricher._collect_compliance_data(_product(note))[flag] is True


@pytest.mark.parametrize("notes, inactive, flag", [
    (("Gluten free. Contains soy.",), (), "soy_free"),
    (("No artificial colors, contains soy lecithin.",), (), "soy_free"),
    (("Free of gluten, but contains milk.",), (), "dairy_free"),
    (("No gluten, dairy or soy.",), ("Soy Lecithin",), "soy_free"),
    (("No sugar. May contain milk.",), (), "dairy_free"),
    # Lactose-free is not dairy-free: lactose-free products can still carry
    # milk protein (whey, casein), which is what a milk allergy reacts to.
    (("No artificial colors or flavors\nNo gluten\nNo lactose",), (), "dairy_free"),
    (("Lactose-free.",), (), "dairy_free"),
    (("No preservatives, yeast, wheat, gluten, lactose, artificial colors or flavors.",), (), "dairy_free"),
])
def test_contradicted_free_from_statement_stays_not_free(enricher, notes, inactive, flag):
    assert enricher._collect_compliance_data(_product(*notes, inactive=inactive))[flag] is False


@pytest.mark.parametrize("ingredient", ["Soy Lecithin", "soy lecithin", "Soya Lecithin"])
def test_soy_lecithin_ingredient_is_detected_as_soy(enricher, ingredient):
    """530 shipped products list soy lecithin; 63 had no soy allergen because
    the alias list held "soya lecithin" and "soy lecithin e322" but not the
    plain name, so the post-promotion hard gate could never fire for it."""
    product = _product(inactive=(ingredient,))
    detected = enricher._collect_contaminant_data(product)["allergens"]["allergens"]
    assert "ALLERGEN_SOY" in {row.get("allergen_id") for row in detected}
