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
