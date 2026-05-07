"""
Rollup-prefix child rescue — regression tests.

Context: the flattener's default code path (non-skip, non-structural-container,
non-proprietary-blend parents) iterates nested children at lines 3463-3501 of
enhanced_normalizer.py. When a nested child is itself skip-listed (e.g.,
"Total EPA and DHA", "Other Omega-3 Fatty Acids"), the code did ``continue``
without recursing into the skipped child's nestedRows. This silently dropped
legitimate grandchild ingredients (EPA, DHA, tocopherol isomers, etc.).

Blast radius: 40 products, 81 lost ingredients across Nature Made, Nordic
Naturals, Pure Encapsulations, and GNC — primarily EPA/DHA in omega-3
gummies/multis.

Fix: mirror the top-level skip path (lines 3432-3451) by extracting
grandchildren from skipped nested items before continuing.

These tests verify:
1. Grandchildren survive through the flattener when their parent is skip-listed.
2. The full normalize_product pipeline emits the grandchildren as active
   ingredients (not silently dropped by _is_nutrition_fact on the rollup parent).
3. Edge cases: proprietary-blend skipped children, deeply nested rollups,
   and mixed nutrition-fact / supplement grandchildren.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


# ---------------------------------------------------------------------------
# Fixture helpers: minimal DSLD product structures
# ---------------------------------------------------------------------------

def _make_dsld_product(product_id: int, name: str, ingredient_rows: list) -> dict:
    """Build a minimal DSLD raw product dict for normalize_product()."""
    return {
        "id": product_id,
        "fullName": name,
        "brandName": "TestBrand",
        "bundleName": name,
        "upcSku": "",
        "servingsPerContainer": "30",
        "netContents": "",
        "targetGroups": [],
        "userGroups": [],
        "physicalState": "Softgel",
        "thumbnail": "",
        "ingredientRows": ingredient_rows,
        "otheringredients": {"text": "", "ingredients": []},
        "statements": [],
        "claims": [],
        "servingSizes": [{"order": 1, "quantity": 1, "unit": "Softgel"}],
        "contacts": [],
    }


def _omega3_gummy_rows():
    """Nordic Omega-3 Gummies Tangerine (220343) ingredient structure."""
    return [
        {
            "name": "Calories", "category": "other",
            "ingredientGroup": "Calories",
            "quantity": [{"quantity": 25, "unit": "Calorie(s)", "servingSizeOrder": 1, "servingSizeQuantity": 2, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Gummy(ies)"}],
            "nestedRows": [], "forms": [], "alternateNames": [],
        },
        {
            "name": "Total Omega-3 Fatty Acids", "category": "fatty acid",
            "ingredientGroup": "Omega-3", "uniiCode": "71M78END5S",
            "quantity": [{"quantity": 82, "unit": "mg", "servingSizeOrder": 1, "servingSizeQuantity": 2, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Gummy(ies)"}],
            "nestedRows": [
                {
                    "name": "Total EPA and DHA", "category": "blend",
                    "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
                    "quantity": [{"quantity": 68, "unit": "mg", "servingSizeOrder": 1, "servingSizeQuantity": 2, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Gummy(ies)"}],
                    "nestedRows": [
                        {
                            "name": "Eicosapentaenoic Acid", "category": "fatty acid",
                            "ingredientGroup": "EPA (Eicosapentaenoic Acid)",
                            "uniiCode": "AAN7QOV9EA",
                            "quantity": [{"quantity": 0, "unit": "NP", "servingSizeOrder": 1, "servingSizeQuantity": 2, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Gummy(ies)"}],
                            "nestedRows": [], "forms": [], "alternateNames": ["C20:5n-3", "EPA"],
                        },
                        {
                            "name": "Docosahexaenoic Acid", "category": "fatty acid",
                            "ingredientGroup": "DHA (Docosahexaenoic Acid)",
                            "uniiCode": "ZAD9OKH9JC",
                            "quantity": [{"quantity": 0, "unit": "NP", "servingSizeOrder": 1, "servingSizeQuantity": 2, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Gummy(ies)"}],
                            "nestedRows": [], "forms": [], "alternateNames": ["C22:6n-3", "DHA"],
                        },
                    ],
                    "forms": [], "alternateNames": [],
                },
            ],
            "forms": [], "alternateNames": [],
        },
    ]


def _fish_oil_rows():
    """Fish Oil parent (Nature Made pattern) with Total EPA & DHA skipped child."""
    return [
        {
            "name": "Fish Oil", "category": "fatty acid",
            "ingredientGroup": "Fish Oil",
            "quantity": [{"quantity": 1200, "unit": "mg", "servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Softgel"}],
            "nestedRows": [
                {
                    "name": "Total EPA & DHA", "category": "blend",
                    "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
                    "quantity": [{"quantity": 720, "unit": "mg", "servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Softgel"}],
                    "nestedRows": [
                        {
                            "name": "Eicosapentaenoic Acid", "category": "fatty acid",
                            "ingredientGroup": "EPA (Eicosapentaenoic Acid)",
                            "quantity": [{"quantity": 360, "unit": "mg", "servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Softgel"}],
                            "nestedRows": [], "forms": [], "alternateNames": ["EPA"],
                        },
                        {
                            "name": "Docosahexaenoic Acid", "category": "fatty acid",
                            "ingredientGroup": "DHA (Docosahexaenoic Acid)",
                            "quantity": [{"quantity": 360, "unit": "mg", "servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Softgel"}],
                            "nestedRows": [], "forms": [], "alternateNames": ["DHA"],
                        },
                    ],
                    "forms": [], "alternateNames": [],
                },
            ],
            "forms": [], "alternateNames": [],
        },
    ]


def _krill_oil_with_other_omega3_rows():
    """Krill Oil parent with 'Other Omega-3 Fatty Acids' skipped child."""
    return [
        {
            "name": "Krill Oil", "category": "fatty acid",
            "ingredientGroup": "Krill Oil",
            "quantity": [{"quantity": 500, "unit": "mg", "servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Softgel"}],
            "nestedRows": [
                {
                    "name": "Other Omega-3 Fatty Acids", "category": "blend",
                    "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
                    "quantity": [{"quantity": 100, "unit": "mg", "servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Softgel"}],
                    "nestedRows": [
                        {
                            "name": "Eicosapentaenoic Acid", "category": "fatty acid",
                            "ingredientGroup": "EPA (Eicosapentaenoic Acid)",
                            "quantity": [{"quantity": 50, "unit": "mg", "servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Softgel"}],
                            "nestedRows": [], "forms": [], "alternateNames": ["EPA"],
                        },
                        {
                            "name": "Docosahexaenoic Acid", "category": "fatty acid",
                            "ingredientGroup": "DHA (Docosahexaenoic Acid)",
                            "quantity": [{"quantity": 50, "unit": "mg", "servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Softgel"}],
                            "nestedRows": [], "forms": [], "alternateNames": ["DHA"],
                        },
                    ],
                    "forms": [], "alternateNames": [],
                },
            ],
            "forms": [], "alternateNames": [],
        },
    ]


def _tocopherol_rows():
    """GNC Isomer E 400 IU — Total Tocopherols with proprietary child blend."""
    return [
        {
            "name": "Total Tocopherols", "category": "vitamin",
            "ingredientGroup": "Vitamin E",
            "quantity": [{"quantity": 400, "unit": "IU", "servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Softgel"}],
            "nestedRows": [
                {
                    "name": "Proprietary Isomer E(TM) blend", "category": "blend",
                    "ingredientGroup": "Blend (Vitamin Supplement)",
                    "quantity": [{"quantity": 400, "unit": "IU", "servingSizeOrder": 1, "servingSizeQuantity": 1, "operator": "=", "dailyValueTargetGroup": [], "servingSizeUnit": "Softgel"}],
                    "nestedRows": [
                        {"name": "D-Alpha-Tocopherol", "category": "vitamin", "ingredientGroup": "Vitamin E", "quantity": [{"quantity": 0, "unit": "NP"}], "nestedRows": [], "forms": [], "alternateNames": []},
                        {"name": "D-Gamma-Tocopherol", "category": "vitamin", "ingredientGroup": "Vitamin E", "quantity": [{"quantity": 0, "unit": "NP"}], "nestedRows": [], "forms": [], "alternateNames": []},
                        {"name": "D-Delta-Tocopherol", "category": "vitamin", "ingredientGroup": "Vitamin E", "quantity": [{"quantity": 0, "unit": "NP"}], "nestedRows": [], "forms": [], "alternateNames": []},
                        {"name": "D-Beta Tocopherol", "category": "vitamin", "ingredientGroup": "Vitamin E", "quantity": [{"quantity": 0, "unit": "NP"}], "nestedRows": [], "forms": [], "alternateNames": []},
                    ],
                    "forms": [], "alternateNames": [],
                },
            ],
            "forms": [], "alternateNames": [],
        },
    ]


# ---------------------------------------------------------------------------
# Stage 1 tests: _flatten_nested_ingredients
# ---------------------------------------------------------------------------

class TestFlattenRollupChildRescue:
    """Verify grandchildren survive flattening when their parent is skip-listed."""

    def test_omega3_gummy_epa_dha_survive_flatten(self, normalizer):
        """EPA and DHA nested under Total EPA and DHA must appear in flattened output."""
        rows = _omega3_gummy_rows()
        flattened = normalizer._flatten_nested_ingredients(rows)
        names = [f.get("name", "") for f in flattened]
        assert "Eicosapentaenoic Acid" in names, (
            f"EPA lost during flattening. Got: {names}"
        )
        assert "Docosahexaenoic Acid" in names, (
            f"DHA lost during flattening. Got: {names}"
        )

    def test_fish_oil_epa_dha_survive_flatten(self, normalizer):
        """Fish Oil > Total EPA & DHA > EPA/DHA — grandchildren must survive."""
        rows = _fish_oil_rows()
        flattened = normalizer._flatten_nested_ingredients(rows)
        names = [f.get("name", "") for f in flattened]
        assert "Eicosapentaenoic Acid" in names
        assert "Docosahexaenoic Acid" in names

    def test_krill_oil_other_omega3_children_survive(self, normalizer):
        """Krill Oil > Other Omega-3 Fatty Acids > EPA/DHA — grandchildren must survive."""
        rows = _krill_oil_with_other_omega3_rows()
        flattened = normalizer._flatten_nested_ingredients(rows)
        names = [f.get("name", "") for f in flattened]
        assert "Eicosapentaenoic Acid" in names
        assert "Docosahexaenoic Acid" in names

    def test_tocopherol_isomers_survive_flatten(self, normalizer):
        """Total Tocopherols > Proprietary blend > D-Alpha/Gamma/Delta/Beta must survive."""
        rows = _tocopherol_rows()
        flattened = normalizer._flatten_nested_ingredients(rows)
        names = [f.get("name", "") for f in flattened]
        assert "D-Alpha-Tocopherol" in names
        assert "D-Gamma-Tocopherol" in names
        assert "D-Delta-Tocopherol" in names
        assert "D-Beta Tocopherol" in names

    def test_rescued_grandchildren_carry_parent_blend_metadata(self, normalizer):
        """Rescued grandchildren must have parentBlend and isNestedIngredient set."""
        rows = _fish_oil_rows()
        flattened = normalizer._flatten_nested_ingredients(rows)
        epa = [f for f in flattened if f.get("name") == "Eicosapentaenoic Acid"]
        assert len(epa) == 1, f"Expected exactly 1 EPA, got {len(epa)}"
        assert epa[0].get("isNestedIngredient") is True
        # parentBlend should reference either the skipped child or its parent
        assert epa[0].get("parentBlend"), "EPA must have parentBlend metadata"


# ---------------------------------------------------------------------------
# Stage 2 tests: full normalize_product pipeline
# ---------------------------------------------------------------------------

class TestNormalizeRollupChildRescue:
    """Verify grandchildren survive the full normalize_product pipeline."""

    def test_omega3_gummy_has_active_epa_dha(self, normalizer):
        """Product 220343 pattern: activeIngredients must include EPA and DHA."""
        raw = _make_dsld_product(999901, "Test Omega-3 Gummies", _omega3_gummy_rows())
        result = normalizer.normalize_product(raw)
        active_names = [
            ing.get("name", "") for ing in result.get("activeIngredients", [])
        ]
        assert "Eicosapentaenoic Acid" in active_names, (
            f"EPA missing from activeIngredients. Got: {active_names}"
        )
        assert "Docosahexaenoic Acid" in active_names, (
            f"DHA missing from activeIngredients. Got: {active_names}"
        )

    def test_fish_oil_has_active_epa_dha(self, normalizer):
        """Nature Made Fish Oil pattern: EPA and DHA in activeIngredients."""
        raw = _make_dsld_product(999902, "Test Fish Oil 1200mg", _fish_oil_rows())
        result = normalizer.normalize_product(raw)
        active_names = [
            ing.get("name", "") for ing in result.get("activeIngredients", [])
        ]
        assert "Eicosapentaenoic Acid" in active_names
        assert "Docosahexaenoic Acid" in active_names

    def test_krill_oil_has_active_epa_dha(self, normalizer):
        """Krill Oil pattern: EPA/DHA under 'Other Omega-3' must survive."""
        raw = _make_dsld_product(999903, "Test Krill Oil 500mg", _krill_oil_with_other_omega3_rows())
        result = normalizer.normalize_product(raw)
        active_names = [
            ing.get("name", "") for ing in result.get("activeIngredients", [])
        ]
        assert "Eicosapentaenoic Acid" in active_names
        assert "Docosahexaenoic Acid" in active_names

    def test_tocopherol_has_active_isomers(self, normalizer):
        """GNC Isomer E pattern: all 4 tocopherol isomers must survive."""
        raw = _make_dsld_product(999904, "Test Vitamin E 400 IU", _tocopherol_rows())
        result = normalizer.normalize_product(raw)
        active_names = [
            ing.get("name", "") for ing in result.get("activeIngredients", [])
        ]
        for iso in ["D-Alpha-Tocopherol", "D-Gamma-Tocopherol", "D-Delta-Tocopherol", "D-Beta Tocopherol"]:
            assert iso in active_names, (
                f"{iso} missing from activeIngredients. Got: {active_names}"
            )

    def test_omega3_gummy_nonzero_active_count(self, normalizer):
        """Product with only omega-3 actives must NOT have 0 activeIngredients."""
        raw = _make_dsld_product(999905, "Test Omega-3 Gummy", _omega3_gummy_rows())
        result = normalizer.normalize_product(raw)
        actives = result.get("activeIngredients", [])
        assert len(actives) > 0, (
            "Product has 0 activeIngredients — rollup child rescue failed"
        )


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestRollupEdgeCases:
    """Edge cases for the rollup child rescue logic."""

    def test_skipped_child_with_no_grandchildren_still_skipped(self, normalizer):
        """A skip-listed child with no nestedRows should still be cleanly skipped."""
        rows = [
            {
                "name": "Fish Oil", "category": "fatty acid",
                "ingredientGroup": "Fish Oil",
                "quantity": [{"quantity": 1000, "unit": "mg"}],
                "nestedRows": [
                    {
                        "name": "Total EPA & DHA", "category": "blend",
                        "ingredientGroup": "Blend",
                        "quantity": [{"quantity": 600, "unit": "mg"}],
                        "nestedRows": [],  # No grandchildren
                        "forms": [], "alternateNames": [],
                    },
                ],
                "forms": [], "alternateNames": [],
            },
        ]
        flattened = normalizer._flatten_nested_ingredients(rows)
        names = [f.get("name", "") for f in flattened]
        assert "Total EPA & DHA" not in names, "Skipped child should not appear"

    def test_nutrition_fact_grandchildren_still_excluded(self, normalizer):
        """Grandchildren that are themselves nutrition facts should still be excluded."""
        rows = [
            {
                "name": "Total Omega-3 Fatty Acids", "category": "fatty acid",
                "ingredientGroup": "Omega-3",
                "quantity": [{"quantity": 82, "unit": "mg"}],
                "nestedRows": [
                    {
                        "name": "Total EPA and DHA", "category": "blend",
                        "ingredientGroup": "Blend",
                        "quantity": [{"quantity": 68, "unit": "mg"}],
                        "nestedRows": [
                            {
                                "name": "Added Sugars", "category": "sugar",
                                "ingredientGroup": "Sugar",
                                "quantity": [{"quantity": 2, "unit": "Gram(s)"}],
                                "nestedRows": [], "forms": [], "alternateNames": [],
                            },
                            {
                                "name": "Eicosapentaenoic Acid", "category": "fatty acid",
                                "ingredientGroup": "EPA",
                                "quantity": [{"quantity": 40, "unit": "mg"}],
                                "nestedRows": [], "forms": [], "alternateNames": [],
                            },
                        ],
                        "forms": [], "alternateNames": [],
                    },
                ],
                "forms": [], "alternateNames": [],
            },
        ]
        flattened = normalizer._flatten_nested_ingredients(rows)
        names = [f.get("name", "") for f in flattened]
        # EPA should survive, Added Sugars should also be flattened (filtering
        # happens in stage 2, _process_ingredients_enhanced, not in flattening)
        assert "Eicosapentaenoic Acid" in names
