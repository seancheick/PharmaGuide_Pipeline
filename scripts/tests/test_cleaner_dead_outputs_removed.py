"""The cleaner emits no field that nothing reads (cleaner root-cause audit RC5, 2026-10-19).

Each removed field had zero readers in scripts/, shell/release scripts and the Flutter app:
`_fromLabelHeader` / `_transparency` (header-expanded inactive rows), `_raw_nested_depth`
(working field; the owned copy is `raw_taxonomy.nested_depth`), `plantPart_source`,
`quantityProvided` (recomputed where blend disclosure needs it) and the product passthrough
`labelRelationships`. Product passthroughs that ARE read stay (`entryDate`, `updatedDate`,
`productVersionCode` by label_record_contract; `offMarket` by the dashboard index).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer

ROW_FIELDS = {"_fromLabelHeader", "_transparency", "_raw_nested_depth", "plantPart_source", "quantityProvided"}


def _qty(amount, unit):
    return [{"servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "quantity": amount,
             "unit": unit, "dailyValueTargetGroup": [], "servingSizeUnit": "Capsule(s)"}]


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.fixture(scope="module")
def cleaned(normalizer):
    # Shape of DSLD 12014 (inactive "Contains Less Than 2% of" header with forms) plus a
    # root botanical and a nested blend.
    raw = {
        "id": "rc5_dead_outputs",
        "fullName": "RC5 Dead Output Fixture",
        "brandName": "Fixture",
        "entryDate": "2020-01-02",
        "updatedDate": "2021-03-04",
        "productVersionCode": "1",
        "offMarket": 0,
        "labelRelationships": [{"type": "Image difference, same product", "labelId": 42}],
        "servingSizes": [{"order": 1, "minQuantity": 1, "maxQuantity": 1, "minDailyServings": 1,
                          "maxDailyServings": 1, "unit": "Capsule(s)", "inSFB": True}],
        "ingredientRows": [
            {"order": 1, "name": "Ginger Root", "category": "botanical", "ingredientGroup": "Ginger",
             "quantity": _qty(250, "mg"), "forms": [], "nestedRows": []},
            # DSLD 174600 shape: a blend holding a sub-blend whose strains carry no amounts.
            {"order": 2, "name": "Raw Probiotic & Enzyme Blend", "category": "blend", "ingredientGroup": "Blend",
             "quantity": _qty(8, "mg"), "forms": [],
             "nestedRows": [
                 {"order": 1, "name": "Lactobacillus Blend", "category": "bacteria",
                  "ingredientGroup": "Lactobacillus (mixed)", "quantity": _qty(0, "NP"), "forms": [],
                  "nestedRows": [
                      {"order": 1, "name": "Lactobacillus bulgaricus", "category": "bacteria",
                       "ingredientGroup": "Lactobacillus bulgaricus", "quantity": _qty(0, "NP"), "forms": [],
                       "nestedRows": []},
                      {"order": 2, "name": "Lactobacillus plantarum", "category": "bacteria",
                       "ingredientGroup": "Lactobacillus plantarum", "quantity": _qty(0, "NP"), "forms": [],
                       "nestedRows": []},
                  ]},
             ]},
        ],
        "otheringredients": {"text": None, "ingredients": [
            {"order": 1, "name": "Cellulose", "category": "fiber", "ingredientGroup": "Cellulose", "forms": []},
            {"order": 2, "name": "Contains Less Than 2% of", "category": "blend", "ingredientGroup": "Blend",
             "forms": [{"order": 1, "name": "Silica", "category": "mineral", "ingredientGroup": "Silicon"},
                       {"order": 2, "name": "Stearic Acid", "category": "fatty acid",
                        "ingredientGroup": "Stearic Acid"}]},
        ]},
    }
    return normalizer.normalize_product(raw)


def _rows(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _rows(child)
    elif isinstance(value, list):
        for child in value:
            yield from _rows(child)


def test_fixture_exercises_every_former_writer(cleaned):
    inactive = {row["name"] for row in cleaned["inactiveIngredients"]}
    assert {"Silica", "Stearic Acid"} <= inactive  # header-expanded rows
    assert any(row.get("plantPart") for row in cleaned["activeIngredients"])
    blend = next(row for row in cleaned["activeIngredients"] if row.get("nestedIngredients"))
    assert len(blend["nestedIngredients"]) == 2


def test_no_dead_row_field_is_emitted(cleaned):
    present = sorted({key for row in _rows(cleaned) for key in row if key in ROW_FIELDS})
    assert present == []


def test_owned_nested_depth_still_recorded(cleaned):
    header_rows = [row for row in cleaned["inactiveIngredients"] if row["name"] in {"Silica", "Stearic Acid"}]
    assert [row["raw_taxonomy"]["nested_depth"] for row in header_rows] == [1, 1]


def test_label_relationships_dropped_and_read_passthroughs_kept(cleaned):
    assert "labelRelationships" not in cleaned
    assert (cleaned["entryDate"], cleaned["updatedDate"], cleaned["productVersionCode"]) == (
        "2020-01-02", "2021-03-04", "1")
    assert "offMarket" in cleaned


def test_blend_disclosure_reads_amounts_not_a_stored_flag(normalizer, cleaned):
    blend = next(row for row in cleaned["activeIngredients"] if row.get("nestedIngredients"))
    disclosure = normalizer._build_proprietary_blend_disclosure([blend])
    assert disclosure["blends"][0]["individualAmounts"] == "Not disclosed"  # strains are NP


@pytest.mark.parametrize("unit", ["", "NP", "np", " unspecified ", None])
def test_an_amount_without_a_real_unit_is_not_disclosed(unit):
    assert not EnhancedDSLDNormalizer._nested_amount_disclosed({"quantity": 50, "unit": unit})


def test_a_positive_amount_with_a_unit_is_disclosed():
    assert EnhancedDSLDNormalizer._nested_amount_disclosed({"quantity": 50, "unit": "mg"})
    assert not EnhancedDSLDNormalizer._nested_amount_disclosed({"quantity": 0, "unit": "mg"})
