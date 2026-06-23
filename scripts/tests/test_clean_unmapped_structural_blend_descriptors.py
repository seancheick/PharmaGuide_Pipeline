"""Structural DSLD blend rows should not pollute the unmapped queue.

These rows are label structure: opaque active blend totals, or inactive
descriptor containers with child forms. They should remain visible for label
fidelity and transparency/safety handling, but they are not IQM gaps.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer


def test_np_active_blend_header_is_display_only_not_unmapped():
    normalizer = EnhancedDSLDNormalizer()
    snapshot = normalizer.get_unmapped_snapshot()

    row = normalizer._process_single_ingredient_enhanced(
        {
            "name": "Brain Health Blend",
            "standardName": "Brain Health Blend",
            "category": None,
            "ingredientGroup": "Blend",
            "quantity": [{"quantity": 0, "unit": "NP"}],
        },
        is_active=True,
    )

    assert row is not None
    assert row["cleaner_row_role"] == "blend_header_total"
    assert row["score_eligible_by_cleaner"] is False
    assert row["score_exclusion_reason"] == "blend_header_total"
    assert row["proprietaryBlend"] is True
    assert normalizer.get_unmapped_delta(snapshot)["unmapped"] == []


def test_inactive_blend_descriptor_with_forms_is_not_unmapped():
    normalizer = EnhancedDSLDNormalizer()
    snapshot = normalizer.get_unmapped_snapshot()

    row = normalizer._process_single_ingredient_enhanced(
        {
            "name": "Creamer",
            "standardName": "Creamer",
            "category": None,
            "ingredientGroup": "Blend (Combination)",
            "quantity": None,
            "forms": [
                {"name": "Maltodextrin"},
                {"name": "Sodium Caseinate"},
                {"name": "Sunflower Oil"},
            ],
        },
        is_active=False,
    )

    assert row is not None
    assert row["cleaner_row_role"] == "inactive"
    assert row["score_eligible_by_cleaner"] is False
    assert row["forms"][0]["name"] == "Maltodextrin"
    assert normalizer.get_unmapped_delta(snapshot)["unmapped"] == []


def test_inactive_blend_descriptor_sequential_path_is_not_unmapped():
    normalizer = EnhancedDSLDNormalizer()
    snapshot = normalizer.get_unmapped_snapshot()

    rows = normalizer._process_ingredients_sequential(
        [
            {
                "name": "Creamer",
                "standardName": "Creamer",
                "category": None,
                "ingredientGroup": "Blend (Combination)",
                "quantity": None,
                "forms": [
                    {"name": "Maltodextrin"},
                    {"name": "Sodium Caseinate"},
                    {"name": "Sunflower Oil"},
                ],
            }
        ]
    )

    assert len(rows) == 1
    assert rows[0]["cleaner_row_role"] == "inactive"
    assert rows[0]["score_eligible_by_cleaner"] is False
    assert rows[0]["forms"][0]["name"] == "Maltodextrin"
    assert normalizer.get_unmapped_delta(snapshot)["unmapped"] == []


def test_parallel_inactive_blend_container_is_not_unmapped():
    normalizer = EnhancedDSLDNormalizer()
    snapshot = normalizer.get_unmapped_snapshot()

    rows = normalizer._process_ingredients_parallel(
        [
            {
                "name": "Fat Blend",
                "standardName": "Fat Blend",
                "category": "blend",
                "ingredientGroup": "Blend (Combination)",
                "quantity": None,
                "forms": [
                    {"name": "Chia seed meal"},
                    {"name": "Flaxseed powder"},
                    {"name": "Safflower Oil"},
                ],
            }
        ]
    )

    assert len(rows) == 1
    assert rows[0]["raw_source_text"] == "Fat Blend"
    assert rows[0]["score_eligible_by_cleaner"] is False
    assert rows[0]["forms"][0]["name"] == "Chia seed meal"
    assert normalizer.get_unmapped_delta(snapshot)["unmapped"] == []


def test_parallel_inactive_source_container_suppressed_but_food_source_remains_unmapped():
    normalizer = EnhancedDSLDNormalizer()
    snapshot = normalizer.get_unmapped_snapshot()

    rows = normalizer._process_ingredients_parallel(
        [
            {
                "name": "Creamer",
                "standardName": "Creamer",
                "category": "other",
                "ingredientGroup": "Creamer",
                "quantity": None,
                "forms": [
                    {"name": "Corn Syrup, Solids"},
                    {"name": "Sodium Caseinate"},
                    {"name": "Sunflower Oil"},
                ],
            },
            {
                "name": "Sweetened Condensed Whole Milk",
                "standardName": "Sweetened Condensed Whole Milk",
                "category": "animal part or source",
                "ingredientGroup": "milk",
                "quantity": None,
                "forms": [
                    {"name": "Sugar"},
                    {"name": "Whole Milk"},
                ],
            },
        ]
    )

    assert [row["raw_source_text"] for row in rows] == [
        "Creamer",
        "Sweetened Condensed Whole Milk",
    ]
    unmapped_names = {
        item["name"] for item in normalizer.get_unmapped_delta(snapshot)["unmapped"]
    }
    assert "Creamer" not in unmapped_names
    assert "Sweetened Condensed Whole Milk" in unmapped_names
