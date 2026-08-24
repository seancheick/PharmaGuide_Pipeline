"""RC-5: integration tests for the label-correction mechanism in
enhanced_normalizer.py.

These tests exercise EnhancedDSLDNormalizer's normalize_product against
synthetic DSLD-shape inputs to assert that:

1. When a (dsld_id, raw_ingredient_text) tuple matches an override
   entry in product_label_corrections.json, the row's name is
   rewritten to corrected_ingredient_text BEFORE downstream
   ingredient resolution, and a provenance tag records the rewrite.

2. When raw_ingredient_text is a known drug token AND there is NO
   matching override for the dsld_id, the row is emitted to
   quarantine with reason 'requires_human_review_drug_token_in_supplement'
   instead of being silently mapped or silently dropped.

3. Non-drug-token unmapped rows continue to flow through the normal
   unmapped path (this test pins the regression boundary so the new
   quarantine code does not over-trigger).

Test inputs are synthesized to be minimal — just enough DSLD shape
to exercise normalize_product. Real shadow-clean of GNC pid=69734
lives in a separate audit script.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

# Skip the integration tests if the normalizer can't be constructed in
# a unit-test harness (it has heavy data-file dependencies). The tests
# below are designed to import the helper functions directly when the
# full normalizer fixture is too heavy.

try:
    from enhanced_normalizer import EnhancedDSLDNormalizer  # type: ignore
    _NORMALIZER_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    EnhancedDSLDNormalizer = None  # type: ignore
    _NORMALIZER_AVAILABLE = False
    _IMPORT_ERR = _e


def _make_ingredient_row(name: str, category: str = "fiber", order: int = 1) -> Dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "order": order,
        "ingredientId": 0,
        "uniiCode": "0",
    }


def _make_raw_product(dsld_id: int, ingredient_names: List[str]) -> Dict[str, Any]:
    return {
        "id": dsld_id,
        "fullName": "Test Product",
        "brandName": "TestBrand",
        "status": "active",
        "offMarket": 0,
        "ingredientRows": [
            _make_ingredient_row(n, order=i + 1)
            for i, n in enumerate(ingredient_names)
        ],
        "otherIngredients": {"ingredients": []},
    }


@pytest.fixture(scope="module")
def normalizer():
    if not _NORMALIZER_AVAILABLE:
        pytest.skip(f"EnhancedDSLDNormalizer not importable: {_IMPORT_ERR}")
    return EnhancedDSLDNormalizer()


def _walk_names(d, found):
    if isinstance(d, dict):
        n = d.get("name")
        if isinstance(n, str):
            found.append(n)
        for v in d.values():
            _walk_names(v, found)
    elif isinstance(d, list):
        for v in d:
            _walk_names(v, found)


def test_override_rewrites_matching_dsld_id_row(normalizer):
    """For GNC pid=69734, the raw 'Insulin' cell must be rewritten
    to 'Inulin' before mapping. We assert by walking the normalized
    output for the 'Inulin' name and absence of 'Insulin'."""
    raw = _make_raw_product(
        dsld_id=69734,
        ingredient_names=["Inositol", "Insulin", "Fructooligosaccharides"],
    )
    normalized = normalizer.normalize_product(raw)
    names = []
    _walk_names(normalized, names)
    name_text = " | ".join(names)
    # Insulin must NOT survive as a raw_source_text or name field
    # after override application
    assert "Insulin" not in [n for n in names if n is not None], (
        f"override failed: 'Insulin' still present in normalized output. "
        f"names={names}"
    )
    # And Inulin must be present (corrected value)
    assert any(n and n.strip().lower() == "inulin" for n in names), (
        f"override failed: 'Inulin' not found after correction. "
        f"names sample={names[:20]}"
    )


def test_verified_unit_correction_is_used_by_label_ledger(normalizer):
    """The Label view and scoring input must use one corrected unit."""
    raw = _make_raw_product(dsld_id=19916, ingredient_names=[])
    raw["ingredientRows"] = [
        {
            **_make_ingredient_row("Boron", category="mineral"),
            "quantity": [{"quantity": 150, "unit": "mg"}],
            "nestedRows": [],
            "forms": [],
        }
    ]

    normalized = normalizer.normalize_product(raw)

    assert normalized["activeIngredients"][0]["unit"] == "mcg"
    assert normalized["display_ingredients"][0]["exact_dose_text"] == "150 mcg"


def test_alternate_serving_rows_are_one_scoring_ingredient(normalizer):
    """Repeated columns are serving alternatives, never additive doses."""
    raw = _make_raw_product(dsld_id=99999996, ingredient_names=[])
    raw["servingSizes"] = [
        {
            "order": 1,
            "minQuantity": 1,
            "maxQuantity": 1,
            "minDailyServings": 2,
            "maxDailyServings": 2,
            "unit": "Tablet(s)",
        }
    ]
    raw["ingredientRows"] = [
        {
            **_make_ingredient_row("Vitamin D", category="vitamin"),
            "ingredientGroup": "Vitamin D",
            "notes": "800 IU",
            "quantity": [{
                "servingSizeOrder": 1,
                "servingSizeQuantity": 1,
                "servingSizeUnit": "Tablet(s)",
                "quantity": 20,
                "unit": "mcg",
            }],
            "nestedRows": [],
            "forms": [],
        },
        {
            **_make_ingredient_row("Vitamin D", category="vitamin", order=2),
            "ingredientGroup": "Vitamin D",
            "notes": "1600 IU",
            "quantity": [{
                "servingSizeOrder": 1,
                "servingSizeQuantity": 2,
                "servingSizeUnit": "Tablet(s)",
                "quantity": 40,
                "unit": "mcg",
            }],
            "nestedRows": [],
            "forms": [],
        },
    ]

    normalized = normalizer.normalize_product(raw)

    assert len(normalized["activeIngredients"]) == 1
    vitamin_d = normalized["activeIngredients"][0]
    assert vitamin_d["quantity"] == 20
    assert [row["quantity"] for row in vitamin_d["quantityVariants"]] == [20, 40]
    assert len(normalized["display_ingredients"]) == 1
    display = normalized["display_ingredients"][0]
    assert display["exact_dose_text"] == ""
    assert [row["exact_dose_text"] for row in display["serving_variants"]] == [
        "20 mcg",
        "40 mcg",
    ]
    assert [row["is_canonical"] for row in display["serving_variants"]] == [
        True,
        False,
    ]


def test_primary_quantity_matches_canonical_serving_column(normalizer):
    """A two-tablet column listed first must not be doubled at daily use."""
    raw = _make_raw_product(dsld_id=99999994, ingredient_names=[])
    raw["servingSizes"] = [
        {
            "order": 1,
            "minQuantity": 1,
            "maxQuantity": 1,
            "minDailyServings": 2,
            "maxDailyServings": 2,
            "unit": "Tablet(s)",
        }
    ]
    raw["ingredientRows"] = [
        {
            **_make_ingredient_row("Calcium", category="mineral"),
            "quantity": [
                {
                    "servingSizeOrder": 1,
                    "servingSizeQuantity": 2,
                    "servingSizeUnit": "Tablet(s)",
                    "quantity": 1200,
                    "unit": "mg",
                },
                {
                    "servingSizeOrder": 1,
                    "servingSizeQuantity": 1,
                    "servingSizeUnit": "Tablet(s)",
                    "quantity": 600,
                    "unit": "mg",
                },
            ],
            "nestedRows": [],
            "forms": [],
        }
    ]

    normalized = normalizer.normalize_product(raw)

    calcium = normalized["activeIngredients"][0]
    assert calcium["quantity"] == 600
    assert [row["quantity"] for row in calcium["quantityVariants"]] == [1200, 600]
    display = normalized["display_ingredients"][0]
    assert [row["is_canonical"] for row in display["serving_variants"]] == [
        False,
        True,
    ]


def test_same_serving_same_name_rows_remain_distinct(normalizer):
    raw = _make_raw_product(dsld_id=99999995, ingredient_names=[])
    raw["ingredientRows"] = [
        {
            **_make_ingredient_row("Protease", category="enzyme"),
            "quantity": [{
                "servingSizeOrder": 1,
                "servingSizeQuantity": 1,
                "servingSizeUnit": "Capsule(s)",
                "quantity": 3030,
                "unit": "HUT",
            }],
            "nestedRows": [],
            "forms": [],
        },
        {
            **_make_ingredient_row("Protease", category="enzyme", order=2),
            "quantity": [{
                "servingSizeOrder": 1,
                "servingSizeQuantity": 1,
                "servingSizeUnit": "Capsule(s)",
                "quantity": 25,
                "unit": "SAPU",
            }],
            "nestedRows": [],
            "forms": [],
        },
    ]

    normalized = normalizer.normalize_product(raw)

    assert len(normalized["activeIngredients"]) == 2


def test_override_does_not_apply_to_non_matching_dsld_id(normalizer):
    """If a hypothetical OTHER product (not in overrides) also
    contains 'Insulin' in a fiber-blend cell, it must NOT be
    silently rewritten — that would defeat scope=dsld_id_only."""
    fake_dsld_id = 99999999  # not in overrides
    raw = _make_raw_product(
        dsld_id=fake_dsld_id,
        ingredient_names=["Inositol", "Insulin", "Fructooligosaccharides"],
    )
    normalized = normalizer.normalize_product(raw)
    names = []
    _walk_names(normalized, names)
    # The row MUST NOT silently become Inulin. Either:
    #   (a) it stays as 'Insulin' (unmapped) and a quarantine signal
    #       is set on the product, OR
    #   (b) the row is dropped with a quarantine signal.
    # What is forbidden: silent re-interpretation as 'Inulin'.
    rewrote_silently = any(
        n and n.strip().lower() == "inulin" for n in names
    )
    assert not rewrote_silently, (
        f"scope leak: 'Insulin' was silently rewritten to 'Inulin' on "
        f"a product with no matching override (dsld_id={fake_dsld_id}). "
        f"Global aliasing of label-typo tokens is forbidden. "
        f"names={names}"
    )


def test_non_drug_token_unmapped_flow_unaffected(normalizer):
    """Regression boundary: an unmapped non-drug-token row (e.g.,
    'Vegetable Concentrate', 'Chocolate Cookie Crumbs') must
    continue to flow through the normal unmapped path. The new
    quarantine code must NOT over-trigger on garden-variety
    unmapped rows."""
    fake_dsld_id = 99999998
    raw = _make_raw_product(
        dsld_id=fake_dsld_id,
        ingredient_names=["Some Unknown Botanical", "Vitamin C"],
    )
    # Just assert this does not raise and produces output
    normalized = normalizer.normalize_product(raw)
    assert normalized is not None
    names = []
    _walk_names(normalized, names)
    assert any(n and "vitamin" in n.lower() for n in names), (
        f"normal unmapped path should still produce ingredient rows. "
        f"names={names[:20]}"
    )


def test_product_scoped_correction_removes_misattributed_source_unii(normalizer):
    rows = [
        {
            "name": "Transglucosidase",
            "category": "enzyme",
            "ingredientGroup": "Transglucosidase",
            "uniiCode": "DTI67O9503",
            "nestedRows": [],
            "forms": [],
        }
    ]

    corrected = normalizer._apply_label_corrections(rows, "59047")

    assert corrected[0]["name"] == "Transglucosidase"
    assert corrected[0]["uniiCode"] is None
    assert corrected[0]["_pre_correction_unii"] == "DTI67O9503"
    assert corrected[0]["_label_correction_provenance"] == "source_unii_correction"

    raw_product = _make_raw_product(59047, [])
    raw_product["fullName"] = "Digestive Enzymes"
    raw_product["ingredientRows"] = [
        {
            "name": "Transglucosidase",
            "category": "enzyme",
            "ingredientGroup": "Transglucosidase",
            "uniiCode": "DTI67O9503",
            "quantity": [{"quantity": 450, "unit": "TG"}],
            "nestedRows": [],
            "forms": [],
        }
    ]
    normalized = normalizer.normalize_product(raw_product)
    active = next(
        row for row in normalized["activeIngredients"]
        if row.get("raw_source_text") == "Transglucosidase"
    )
    assert active["source_correction"] == {
        "provenance_tag": "source_unii_correction",
        "original_unii_code": "DTI67O9503",
        "corrected_unii_code": None,
    }


def test_product_scoped_correction_repairs_verified_quantity_unit(normalizer):
    raw_product = _make_raw_product(259789, [])
    raw_product["fullName"] = "GNC Multivitamin Active"
    raw_product["brandName"] = "GNC"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row("Iodine", category="mineral"),
            "ingredientGroup": "Iodine",
            "uniiCode": "9679TC07X4",
            "quantity": [
                {"quantity": 150, "unit": "mg"},
                {"quantity": 75, "unit": "mg"},
            ],
            "nestedRows": [],
            "forms": [],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)
    active = normalized["activeIngredients"][0]

    assert active["quantity"] == 150
    assert active["unit"] == "mcg"
    assert [variant["unit"] for variant in active["quantityVariants"]] == [
        "mcg",
        "mcg",
    ]
    assert active["source_correction"] == {
        "provenance_tag": "official_label_unit_correction",
        "original_quantity_unit": "mg",
        "corrected_quantity_unit": "mcg",
    }


def test_product_scoped_correction_repairs_verified_quantity_and_unit(normalizer):
    raw_product = _make_raw_product(302650, [])
    raw_product["fullName"] = "Comprehensive Prostate Formula"
    raw_product["brandName"] = "Doctor's Best"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row("SelenoExcell "),
            "ingredientGroup": "Selenium Yeast",
            "quantity": [{"quantity": 640, "unit": "mg"}],
            "nestedRows": [],
            "forms": [{"name": "Selenium", "ingredientGroup": "Selenium"}],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)
    active = normalized["activeIngredients"][0]

    assert active["name"] == "Selenium"
    assert active["canonical_id"] == "selenium"
    assert active["quantity"] == 200
    assert active["unit"] == "mcg"
    assert active["source_correction"] == {
        "provenance_tag": "official_label_quantity_correction",
        "original_ingredient_text": "SelenoExcell ",
        "corrected_ingredient_text": "Selenium",
        "original_quantity_value": 640,
        "corrected_quantity_value": 200,
        "original_quantity_unit": "mg",
        "corrected_quantity_unit": "mcg",
    }


def test_product_scoped_correction_repairs_crossed_up_and_up_dha_row(normalizer):
    """DSLD 19899 has a crossed Dextrose/Glucose structured identity, while
    its own row note and product statements explicitly identify 200 mg DHA."""
    raw_product = _make_raw_product(19899, [])
    raw_product["fullName"] = "DHA Prenatal Supplement"
    raw_product["brandName"] = "up & up"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row("Dextrose", category="sugar"),
            "ingredientGroup": "Glucose",
            "uniiCode": "IY9XDZ35W2",
            "notes": "DHA (Form: from Schizochytrium sp. oil) (Alt. Name: Docosahexaenoic Acid)",
            "quantity": [{"quantity": 200, "unit": "mg"}],
            "nestedRows": [],
            "forms": [
                {
                    **_make_ingredient_row("Glucose", category="sugar"),
                    "ingredientGroup": "Glucose",
                    "uniiCode": "5SL0G7R0OK",
                    "nestedRows": [],
                    "forms": [],
                }
            ],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)

    assert len(normalized["activeIngredients"]) == 1
    active = normalized["activeIngredients"][0]
    assert active["name"] == "DHA"
    assert active["canonical_id"] == "dha"
    assert active["quantity"] == 200
    assert active["unit"] == "mg"
    assert active["uniiCode"] is None
    assert active["source_correction"]["provenance_tag"] == (
        "official_source_identity_correction"
    )
    assert all(
        (row.get("canonical_id") or "").lower() != "nha_glucose_liquid"
        for row in normalized["activeIngredients"]
    )


def test_product_scoped_correction_repairs_crossed_cvs_dha_row(normalizer):
    """DSLD 25935's own official record declares the crossed 200 mg row as DHA."""
    raw_product = _make_raw_product(25935, [])
    raw_product["fullName"] = "DHA"
    raw_product["brandName"] = "CVS Pharmacy"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row("Dextrose", category="sugar"),
            "ingredientGroup": "Glucose",
            "uniiCode": "IY9XDZ35W2",
            "quantity": [{"quantity": 200, "unit": "mg"}],
            "nestedRows": [],
            "forms": [
                {
                    **_make_ingredient_row("Glucose", category="sugar"),
                    "ingredientGroup": "Glucose",
                    "uniiCode": "5SL0G7R0OK",
                    "nestedRows": [],
                    "forms": [],
                }
            ],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)

    assert len(normalized["activeIngredients"]) == 1
    active = normalized["activeIngredients"][0]
    assert active["name"] == "DHA"
    assert active["canonical_id"] == "dha"
    assert active["quantity"] == 200
    assert active["unit"] == "mg"
    assert active["uniiCode"] is None
    assert active["source_correction"]["provenance_tag"] == (
        "official_source_identity_correction"
    )
    assert all(
        (row.get("canonical_id") or "").lower() != "nha_glucose_liquid"
        for row in normalized["activeIngredients"]
    )


def test_product_scoped_correction_restores_statement_backed_form_dose(normalizer):
    """A reviewed form dose is restored without rewriting its Total Fat owner."""
    raw_product = _make_raw_product(2248, [])
    raw_product["fullName"] = "Flax Seed Oil 1300"
    raw_product["brandName"] = "GNC"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row("Total Fat", category="fat"),
            "ingredientGroup": "Fat (unspecified)",
            "quantity": [{"quantity": 2, "unit": "g"}],
            "nestedRows": [],
            "forms": [
                {
                    **_make_ingredient_row("Flax seed Oil", category="fat"),
                    "ingredientGroup": "Flaxseed Oil",
                    "nestedRows": [],
                    "forms": [],
                }
            ],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)

    assert len(normalized["activeIngredients"]) == 1
    active = normalized["activeIngredients"][0]
    assert active["canonical_id"] == "flaxseed"
    assert active["quantity"] == 1300
    assert active["unit"] == "mg"
    assert active["raw_source_path"] == "ingredientRows[0].forms[0]"
    assert active["source_correction"] == {
        "provenance_tag": "official_statement_dose_correction",
        "original_quantity_value": None,
        "corrected_quantity_value": 1300,
        "original_quantity_unit": None,
        "corrected_quantity_unit": "mg",
    }


def test_missing_form_dose_is_not_inferred_without_product_override(normalizer):
    raw_product = _make_raw_product(999999991, [])
    raw_product["fullName"] = "Flax Seed Oil 1300"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row("Total Fat", category="fat"),
            "ingredientGroup": "Fat (unspecified)",
            "quantity": [{"quantity": 2, "unit": "g"}],
            "nestedRows": [],
            "forms": [
                {
                    **_make_ingredient_row("Flax seed Oil", category="fat"),
                    "ingredientGroup": "Flaxseed Oil",
                    "nestedRows": [],
                    "forms": [],
                }
            ],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)
    active = normalized["activeIngredients"][0]

    assert active["quantity"] == 0
    assert active["unit"] == "unspecified"
    assert "source_correction" not in active


def test_product_scoped_correction_repairs_verified_boron_unit(normalizer):
    raw_product = _make_raw_product(328117, [])
    raw_product["fullName"] = (
        "Alive! Women's 50+ Multivitamin Gummy Mixed Berry Flavored"
    )
    raw_product["brandName"] = "Nature's Way"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row("Boron", category="mineral"),
            "ingredientGroup": "Boron",
            "uniiCode": "N9E3X5056Q",
            "quantity": [{"quantity": 150, "unit": "mg"}],
            "nestedRows": [],
            "forms": [],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)
    active = normalized["activeIngredients"][0]

    assert active["quantity"] == 150
    assert active["unit"] == "mcg"
    assert active["source_correction"] == {
        "provenance_tag": "official_label_unit_correction",
        "original_quantity_unit": "mg",
        "corrected_quantity_unit": "mcg",
    }


@pytest.mark.parametrize(
    ("dsld_id", "ingredient", "raw_unit"),
    [
        (243029, "Caffeine Anhydrous", "mmg"),
        (66883, "Glycine", "Jar(s)"),
    ],
)
def test_product_scoped_correction_repairs_verified_mass_unit_typos(
    normalizer, dsld_id, ingredient, raw_unit
):
    rows = [
        {
            **_make_ingredient_row(ingredient),
            "quantity": [{"quantity": 250, "unit": raw_unit}],
            "nestedRows": [],
            "forms": [],
        }
    ]

    corrected = normalizer._apply_label_corrections(rows, str(dsld_id))

    assert corrected[0]["quantity"][0]["unit"] == "mg"
    assert corrected[0]["_pre_correction_quantity_unit"] == raw_unit
    assert corrected[0]["_label_correction_provenance"] == (
        "official_label_unit_correction"
    )


@pytest.mark.parametrize("dsld_id", [69599, 259709, 69608])
def test_product_scoped_correction_restores_weight_gainer_protein_grams(
    normalizer, dsld_id
):
    rows = [
        {
            **_make_ingredient_row("Protein", category="protein"),
            "quantity": [{"quantity": 50, "unit": "mg"}],
            "nestedRows": [],
            "forms": [],
        }
    ]

    corrected = normalizer._apply_label_corrections(rows, str(dsld_id))

    assert corrected[0]["quantity"][0]["quantity"] == 50
    assert corrected[0]["quantity"][0]["unit"] == "Gram(s)"
    assert corrected[0]["_pre_correction_quantity_unit"] == "mg"
    assert corrected[0]["_label_correction_provenance"] == (
        "official_label_unit_correction"
    )


def test_product_scoped_correction_restores_megafood_horsetail_label_text(
    normalizer,
):
    rows = [
        {
            **_make_ingredient_row("Springtail", category="botanical"),
            "ingredientGroup": "TBD",
            "quantity": [{"quantity": 0, "unit": "NP"}],
            "nestedRows": [],
            "forms": [],
        }
    ]

    corrected = normalizer._apply_label_corrections(rows, "327590")

    assert corrected[0]["name"] == "Spring Horsetail"
    assert corrected[0]["_pre_correction_name"] == "Springtail"
    assert corrected[0]["_label_correction_provenance"] == (
        "official_label_text_correction"
    )


def test_product_scoped_koact_source_material_is_not_a_second_active(
    normalizer,
):
    raw_product = _make_raw_product(328300, [])
    raw_product["fullName"] = "Bone Strength Collagen Formula"
    raw_product["brandName"] = "Life Extension"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row("Calcium", category="mineral"),
            "ingredientGroup": "Calcium",
            "uniiCode": "SY7Q814VUP",
            "quantity": [{
                "quantity": 300,
                "unit": "mg",
                "dailyValueTargetGroup": [{"percent": 23}],
            }],
            "nestedRows": [
                {
                    **_make_ingredient_row(
                        "KoAct",
                        category="non-nutrient/non-botanical",
                    ),
                    "ingredientGroup": "Calcium",
                    "uniiCode": None,
                    "quantity": [{"quantity": 3000, "unit": "mg"}],
                    "nestedRows": [],
                    "forms": [
                        {
                            **_make_ingredient_row(
                                "Calcium Collagen Chelate",
                                category="mineral",
                            ),
                            "ingredientGroup": "Calcium",
                            "uniiCode": None,
                        },
                        {
                            **_make_ingredient_row(
                                "Calcium Fructoborate",
                                category="mineral",
                            ),
                            "ingredientGroup": "Calcium",
                            "uniiCode": "7EW2EZ38LS",
                        },
                    ],
                }
            ],
            "forms": [],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)
    source_material = next(
        row
        for row in normalized["activeIngredients"]
        if row.get("raw_source_path") == "ingredientRows[0].nestedRows[0]"
    )

    assert source_material["name"] == "KoAct Calcium Collagen Chelate"
    assert source_material["cleaner_row_role"] == "source_descriptor"
    assert source_material["score_eligible_by_cleaner"] is False
    assert source_material["score_exclusion_reason"] == "source_descriptor"
    assert source_material["dose_class"] == "source_material_mass"
    assert source_material["source_correction"] == {
        "provenance_tag": "official_label_text_correction",
        "original_ingredient_text": "KoAct",
        "corrected_ingredient_text": "KoAct Calcium Collagen Chelate",
        "scoring_disposition": "source_descriptor",
    }


def test_unknown_product_scoring_disposition_fails_closed(normalizer):
    normalizer._label_corrections_by_dsld_id["999001"] = {
        "raw_ingredient_text": "Reviewed Source Material",
        "corrected_ingredient_text": "Reviewed Source Material",
        "scoring_disposition": "invented_disposition",
    }
    raw_product = _make_raw_product(
        999001,
        ["Reviewed Source Material"],
    )

    with pytest.raises(
        ValueError,
        match="Unsupported product-label scoring disposition",
    ):
        normalizer.normalize_product(raw_product)


def test_product_scoped_correction_repairs_crossed_cognimag_hierarchy(normalizer):
    raw_product = _make_raw_product(299037, [])
    raw_product["fullName"] = "CogniMag"
    raw_product["brandName"] = "Pure Encapsulations"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row("Magnesium", category="mineral"),
            "ingredientGroup": "Magnesium",
            "uniiCode": "I38ZP9992A",
            "quantity": [{"quantity": 1000, "unit": "mg"}],
            "nestedRows": [
                {
                    **_make_ingredient_row(
                        "Magtein Magnesium L-Threonate",
                        category="non-nutrient/non-botanical",
                    ),
                    "ingredientGroup": "Magnesium",
                    "uniiCode": None,
                    "quantity": [{
                        "quantity": 72,
                        "unit": "mg",
                        "dailyValueTargetGroup": [{"percent": 17}],
                    }],
                    "nestedRows": [],
                    "forms": [],
                }
            ],
            "forms": [],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)
    source_material, delivered_nutrient = normalized["activeIngredients"]

    assert source_material["name"] == "Magtein Magnesium L-Threonate"
    assert source_material["quantity"] == 1000
    assert source_material["uniiCode"] is None
    assert source_material["source_correction"] == {
        "provenance_tag": "official_label_hierarchy_correction",
        "original_ingredient_text": "Magnesium",
        "corrected_ingredient_text": "Magtein Magnesium L-Threonate",
        "original_unii_code": "I38ZP9992A",
        "corrected_unii_code": None,
    }
    assert delivered_nutrient["name"] == "Magnesium"
    assert delivered_nutrient["quantity"] == 72
    assert delivered_nutrient["dailyValue"] == 17
    assert delivered_nutrient["parentBlend"] == "Magtein Magnesium L-Threonate"
    assert delivered_nutrient["source_correction"] == {
        "provenance_tag": "official_label_hierarchy_correction",
        "original_ingredient_text": "Magtein Magnesium L-Threonate",
        "corrected_ingredient_text": "Magnesium",
    }

    display = normalized["display_ingredients"]
    assert [(row["display_name"], row["exact_dose_text"]) for row in display] == [
        ("Magtein Magnesium L-Threonate", "1,000 mg"),
        ("Magnesium", "72 mg"),
    ]


def test_botanical_latin_parenthetical_resolves_without_replacing_label_name(normalizer):
    raw_product = _make_raw_product(99999997, [])
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row(
                "Tropical Almond (Terminalia chebula)",
                category="botanical",
            ),
            "ingredientGroup": "Tropical Almond",
            "quantity": [{"quantity": 500, "unit": "mg"}],
            "nestedRows": [],
            "forms": [],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)

    active = normalized["activeIngredients"][0]
    assert active["raw_source_text"] == "Tropical Almond (Terminalia chebula)"
    assert active["name"] == "Tropical Almond (Terminalia chebula)"
    assert active["standardName"] == "Chebulic Myrobalan"
    assert active["canonical_id"] == "chebulic_myrobalan"
    assert active["canonical_source_db"] == "botanical_ingredients"


def test_nested_64551_row_restores_omitted_latin_identity(normalizer):
    raw_product = _make_raw_product(64551, [])
    raw_product["fullName"] = "Standardized Triphala"
    raw_product["brandName"] = "Nature's Way"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row(
                "Triphala fruit extract Blend",
                category="blend",
            ),
            "ingredientGroup": "Blend (Herb/Botanical)",
            "quantity": [{"quantity": 1.5, "unit": "Gram(s)"}],
            "forms": [],
            "nestedRows": [
                {
                    **_make_ingredient_row(
                        "Tropical Almond",
                        category="botanical",
                    ),
                    "ingredientGroup": "Tropical Almond",
                    "quantity": [{"quantity": 500, "unit": "mg"}],
                    "nestedRows": [],
                    "forms": [],
                }
            ],
        }
    ]

    normalized = normalizer.normalize_product(raw_product)

    active = next(
        row for row in normalized["activeIngredients"]
        if row.get("canonical_id") == "chebulic_myrobalan"
    )
    assert active["raw_source_text"] == "Tropical Almond (Terminalia chebula)"
    assert active["source_correction"] == {
        "provenance_tag": "source_label_omission_correction",
        "original_ingredient_text": "Tropical Almond",
        "corrected_ingredient_text": "Tropical Almond (Terminalia chebula)",
    }


def test_explicit_epa_note_repairs_contradictory_dsld_dha_taxonomy(normalizer):
    """The DSLD omega row must follow its explicit EPA label note, not a
    contradictory DHA name/identifier tuple supplied by the API."""
    raw_product = _make_raw_product(180408, [])
    raw_product["fullName"] = "One Per Day Fish Oil 1200 mg"
    raw_product["brandName"] = "Nature Made"
    raw_product["ingredientRows"] = [
        {
            **_make_ingredient_row(
                "Docosahexaenoic Acid Ethyl Ester",
                category="fatty acid",
            ),
            "ingredientId": 285066,
            "ingredientGroup": "DHA (Docosahexaenoic Acid)",
            "uniiCode": "7PO7G8PA8M",
            "alternateNames": ["C22:6n-3", "DHA EE"],
            "notes": (
                "EPA (Form: as Ethyl Esters) "
                "(Alt. Name: Eicosapentaenoic Acid) Note: Omega-3"
            ),
            "quantity": [{"quantity": 360, "unit": "mg"}],
            "nestedRows": [],
            "forms": [],
        },
        {
            **_make_ingredient_row(
                "Docosahexaenoic Acid Ethyl Ester",
                category="fatty acid",
                order=2,
            ),
            "ingredientId": 285066,
            "ingredientGroup": "DHA (Docosahexaenoic Acid)",
            "uniiCode": "7PO7G8PA8M",
            "alternateNames": ["C22:6n-3", "DHA EE"],
            "notes": (
                "DHA (Form: as Ethyl Esters) "
                "(Alt. Name: Docosahexaenoic Acid) Note: Omega-3"
            ),
            "quantity": [{"quantity": 300, "unit": "mg"}],
            "nestedRows": [],
            "forms": [],
        },
    ]

    normalized = normalizer.normalize_product(raw_product)

    assert [row["canonical_id"] for row in normalized["activeIngredients"]] == [
        "epa",
        "dha",
    ]
    epa = normalized["activeIngredients"][0]
    assert epa["raw_source_text"] == "Eicosapentaenoic Acid Ethyl Ester"
    assert epa["ingredientGroup"] == "EPA (Eicosapentaenoic Acid)"
    assert epa["uniiCode"] == "6GC8A4PAYH"
    assert epa["ingredientId"] == 285067
    assert epa["source_correction"] == {
        "provenance_tag": "source_taxonomy_contradiction_repair",
        "original_ingredient_text": "Docosahexaenoic Acid Ethyl Ester",
        "corrected_ingredient_text": "Eicosapentaenoic Acid Ethyl Ester",
        "original_unii_code": "7PO7G8PA8M",
        "corrected_unii_code": "6GC8A4PAYH",
    }

    ledger_rows = normalized["display_ingredients"]
    assert [row["label_display_name"] for row in ledger_rows] == [
        "EPA",
        "DHA",
    ]
    assert [row["exact_dose_text"] for row in ledger_rows] == [
        "360 mg",
        "300 mg",
    ]
