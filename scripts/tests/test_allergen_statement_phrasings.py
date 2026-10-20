"""Allergen statements in the shapes real labels use are read.

2026-10-19 corpus census: "Allergen information: Fish, Soy" (~200 products),
facility and equipment wording outside the three fixed patterns ("Processed in
a facility with products that contain egg, fish, ...", "Manufactured on
equipment which processes dairy", ~250 products), and a declaration after a
negator in the same clause or on a later line of one statement (3 products)
produced no allergen flag. Every string below is from a corpus label.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


def _hits(enricher, statement):
    product = {
        "id": "99990", "fullName": "Test",
        "statements": [{"type": "Precautions", "notes": statement}],
        "activeIngredients": [{"name": "Vitamin C"}], "inactiveIngredients": [],
    }
    return {h["allergen_id"]: h["presence_type"]
            for h in SupplementEnricherV3._collect_contaminant_data(enricher, product)["allergens"]["allergens"]}


@pytest.mark.parametrize("pid,statement,expected,presence", [
    ("174772", "Processed in a facility with products that contain egg, fish, shellfish, soy and tree nuts.",
     {"ALLERGEN_EGGS", "ALLERGEN_FISH", "ALLERGEN_CRUSTACEANS", "ALLERGEN_SOY", "ALLERGEN_TREE_NUTS"}, "facility_warning"),
    ("241286", "Contains naturally occurring iodine.\t\nManufactured on equipment that may process soy, wheat and/or fish (anchovy, sardine).",
     {"ALLERGEN_SOY", "ALLERGEN_WHEAT", "ALLERGEN_FISH"}, "facility_warning"),
    ("297681", "Made without dairy or soy ingredients, peanut, or shellfish. Manufactured in a facility that also process fish.\r\n",
     {"ALLERGEN_FISH"}, "facility_warning"),
    ("206889", "Probiotic materials manufactured on equipment which processes dairy.", {"ALLERGEN_MILK"}, "facility_warning"),
    ("239602", "The facility processes some ingredients that contain trace amounts of milk, egg, fish, crustacean shellfish, tree nuts, wheat, peanuts, and soy.",
     {"ALLERGEN_MILK", "ALLERGEN_EGGS", "ALLERGEN_FISH", "ALLERGEN_CRUSTACEANS", "ALLERGEN_TREE_NUTS", "ALLERGEN_WHEAT", "ALLERGEN_PEANUTS", "ALLERGEN_SOY"}, "facility_warning"),
    ("312976", "Allergen Information: Fish, Soy", {"ALLERGEN_FISH", "ALLERGEN_SOY"}, "contains"),
    ("294367", "Allergy information: soy", {"ALLERGEN_SOY"}, "contains"),
    ("339541", "Allergens: milk.", {"ALLERGEN_MILK"}, "contains"),
])
def test_real_statement_shapes_are_read(enricher, pid, statement, expected, presence):
    hits = _hits(enricher, statement)
    assert expected <= set(hits)
    assert {hits[a] for a in expected} == {presence}


@pytest.mark.parametrize("pid,statement,absent", [
    ("217191", "Processed in a facility free from gluten, dairy, soy, nuts, and fish.", {"ALLERGEN_FISH", "ALLERGEN_MILK", "ALLERGEN_SOY"}),
    ("297681", "Made without dairy or soy ingredients, peanut, or shellfish. Manufactured in a facility that also process fish.",
     {"ALLERGEN_MILK", "ALLERGEN_SOY", "ALLERGEN_PEANUTS", "ALLERGEN_CRUSTACEANS"}),
    ("258717", "Not manufactured with: Milk, eggs, fish, crustacean shellfish, peanuts, wheat, soy or gluten.",
     {"ALLERGEN_MILK", "ALLERGEN_EGGS", "ALLERGEN_FISH", "ALLERGEN_WHEAT", "ALLERGEN_SOY"}),
    (None, "This facility does not process peanuts or tree nuts.", {"ALLERGEN_PEANUTS", "ALLERGEN_TREE_NUTS"}),
    (None, "Produced in a peanut-free facility.", {"ALLERGEN_PEANUTS"}),
])
def test_negated_facility_and_free_from_wording_is_not_flagged(enricher, pid, statement, absent):
    assert not absent & set(_hits(enricher, statement))


def test_a_later_line_of_one_statement_is_its_own_clause(enricher):
    # 328850: "No added sugar" on one line swallowed the whey declaration on the next.
    hits = _hits(enricher, "Gluten-Free\r\nNon-GMO\r\nNo added sugar\r\nThis product contains whey protein isolate from cows not treated with growth hormone (rBST).")
    assert hits.get("ALLERGEN_MILK") == "contains"


@pytest.mark.parametrize("statement,expected,absent", [
    ("Contains no artificial colors, contains soy", "ALLERGEN_SOY", None),
    ("Free of gluten and wheat. Contains milk.", "ALLERGEN_MILK", "ALLERGEN_WHEAT"),
    ("Contains no artificial colors. Contains soy.", "ALLERGEN_SOY", None),
    ("What's more, Macros doesn't contains soy, dairy or whey protein ingredients.", None, "ALLERGEN_SOY"),
    ("Contains milk and doesn't contain gluten", "ALLERGEN_MILK", "ALLERGEN_WHEAT"),
])
def test_a_declaration_after_a_negator_is_still_read(enricher, statement, expected, absent):
    hits = _hits(enricher, statement)
    if expected:
        assert expected in hits
    if absent:
        assert absent not in hits
