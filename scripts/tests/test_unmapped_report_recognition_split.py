"""Safety/additive-recognized rows must not pollute the unmapped *identity* report.

A label like 'Mannitol' (harmful_additives) or 'Sulbutiamine' (banned_recalled)
gets no IQM identity by design (canonical_id never comes from safety DBs), yet it
was being logged into unmapped_active/inactive_ingredients.json — a false
"add this to the identity DB" gap that inflates the triage queue.

These rows are now tagged ``recognized_non_identity`` by the normalizer and routed
by the tracker into a separate ``recognized_non_identity_ingredients.json`` bucket,
excluded from the unmapped lists. They are NOT dropped (a watchlist row could still
be a legitimate active that genuinely needs an IQM entry) — only re-categorized.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer
from unmapped_ingredient_tracker import UnmappedIngredientTracker


def test_tracker_routes_recognized_rows_out_of_unmapped_lists(tmp_path):
    tracker = UnmappedIngredientTracker(tmp_path)
    tracker.process_unmapped_ingredients(
        {"Mannitol": 4, "Genuinely Unknown Active": 2},
        {"Genuinely Unknown Active"},
        {
            "Mannitol": {
                "is_active": False,
                "recognized_non_identity": True,
                "recognition_standard_name": "Sugar Alcohols (Polyols)",
                "recognition_type": "harmful_additive",
            },
            "Genuinely Unknown Active": {"is_active": True},
        },
    )
    tracker.save_tracking_files()

    inactive = json.loads((tmp_path / "unmapped_inactive_ingredients.json").read_text())
    active = json.loads((tmp_path / "unmapped_active_ingredients.json").read_text())
    recognized = json.loads((tmp_path / "recognized_non_identity_ingredients.json").read_text())

    # recognized additive excluded from BOTH identity-gap lists
    assert "Mannitol" not in inactive["unmapped_ingredients"]
    assert "Mannitol" not in active["unmapped_ingredients"]
    # genuinely-unknown active is still reported as a true gap
    assert active["unmapped_ingredients"]["Genuinely Unknown Active"] == 2
    # recognized row captured separately, with audit context, not lost
    row = recognized["recognized_ingredients"]["Mannitol"]
    assert row["occurrences"] == 4
    assert row["recognition_standard_name"] == "Sugar Alcohols (Polyols)"
    assert recognized["metadata"]["total_recognized"] == 1


def test_normalizer_tracking_counts_only_true_identity_gaps(tmp_path):
    normalizer = EnhancedDSLDNormalizer()
    normalizer.set_output_directory(tmp_path)
    normalizer.unmapped_ingredients.update({
        "Mannitol": 4,
        "No-dose Blend Child": 3,
        "Genuinely Unknown Active": 2,
    })
    normalizer.unmapped_details.update({
        "Mannitol": {
            "is_active": False,
            "recognized_non_identity": True,
            "recognition_standard_name": "Sugar Alcohols (Polyols)",
            "recognition_type": "harmful_additive",
        },
        "No-dose Blend Child": {
            "is_active": True,
            "non_scoreable_cleaner_row": True,
            "cleaner_row_role": "nested_display_only",
            "score_exclusion_reason": "nested_display_only",
        },
        "Genuinely Unknown Active": {"is_active": True},
    })

    result = normalizer.process_and_save_unmapped_tracking()

    assert result == {
        "active_count": 1,
        "inactive_count": 0,
        "total_count": 1,
        "recognized_count": 1,
        "non_scoreable_count": 1,
    }


def test_tracker_routes_score_excluded_rows_out_of_unmapped_lists(tmp_path):
    tracker = UnmappedIngredientTracker(tmp_path)
    tracker.process_unmapped_ingredients(
        {"B. lactis BS01": 3, "Genuinely Unknown Active": 2},
        {"B. lactis BS01", "Genuinely Unknown Active"},
        {
            "B. lactis BS01": {
                "is_active": True,
                "non_scoreable_cleaner_row": True,
                "cleaner_row_role": "nested_display_only",
                "score_exclusion_reason": "nested_display_only",
            },
            "Genuinely Unknown Active": {"is_active": True},
        },
    )
    tracker.save_tracking_files()

    active = json.loads((tmp_path / "unmapped_active_ingredients.json").read_text())
    inactive = json.loads((tmp_path / "unmapped_inactive_ingredients.json").read_text())
    excluded = json.loads((tmp_path / "non_scoreable_unmapped_ingredients.json").read_text())

    assert "B. lactis BS01" not in active["unmapped_ingredients"]
    assert "B. lactis BS01" not in inactive["unmapped_ingredients"]
    assert active["unmapped_ingredients"]["Genuinely Unknown Active"] == 2

    row = excluded["ingredients"]["B. lactis BS01"]
    assert row["occurrences"] == 3
    assert row["cleaner_row_role"] == "nested_display_only"
    assert row["score_exclusion_reason"] == "nested_display_only"
    assert row["is_active"] is True


def test_backward_compatible_when_no_recognition_flag(tmp_path):
    """Details without the recognition flag behave exactly as before."""
    tracker = UnmappedIngredientTracker(tmp_path)
    tracker.process_unmapped_ingredients(
        {"Chopchinee": 2, "Unknown Inactive": 1},
        {"Chopchinee"},
        {"Chopchinee": {"is_active": True}, "Unknown Inactive": {"is_active": False}},
    )
    tracker.save_tracking_files()
    active = json.loads((tmp_path / "unmapped_active_ingredients.json").read_text())
    inactive = json.loads((tmp_path / "unmapped_inactive_ingredients.json").read_text())
    recognized = json.loads((tmp_path / "recognized_non_identity_ingredients.json").read_text())
    excluded = json.loads((tmp_path / "non_scoreable_unmapped_ingredients.json").read_text())
    assert active["unmapped_ingredients"]["Chopchinee"] == 2
    assert inactive["unmapped_ingredients"]["Unknown Inactive"] == 1
    assert recognized["metadata"]["total_recognized"] == 0
    assert excluded["metadata"]["total_excluded"] == 0


def test_normalizer_flags_safety_recognized_rows_as_non_identity():
    n = EnhancedDSLDNormalizer()
    detail = n._build_unmapped_detail("Mannitol", [], is_active=False)
    assert detail.get("recognized_non_identity") is True
    assert detail.get("recognition_standard_name") == "Sugar Alcohols (Polyols)"


@pytest.mark.parametrize(
    ("label", "standard_name", "recognition_type"),
    [
        ("Soy Protein, Hydrolyzed", "Soy & Soy Lecithin", "allergen"),
        ("Sweetened Condensed Whole Milk", "Milk", "allergen"),
        ("Whey, Solids", "Milk", "allergen"),
        ("Chopped Peanuts", "Peanuts", "allergen"),
        ("Wheat Isolate", "Wheat", "allergen"),
        ("Wheat Berry", "Wheat", "allergen"),
        ("Oats, Myceliated", "Oats", "allergen"),
        ("myceliated Oats", "Oats", "allergen"),
        ("Titanium Dioxide Mineral Whitener", "Titanium Dioxide (E171)", "banned"),
    ],
)
def test_normalizer_flags_allergen_and_high_risk_label_variants_as_non_identity(
    label,
    standard_name,
    recognition_type,
):
    n = EnhancedDSLDNormalizer()

    detail = n._build_unmapped_detail(
        label,
        [],
        is_active=False,
    )
    assert detail.get("recognized_non_identity") is True
    assert detail.get("recognition_standard_name") == standard_name
    assert detail.get("recognition_type") == recognition_type


def test_other_ingredient_reverse_index_keeps_arabinose_identity():
    n = EnhancedDSLDNormalizer()

    assert n._resolve_canonical_identity(
        "Arabinose",
        raw_name="Arabinose",
    ) == ("PII_ARABINOSE", "other_ingredients")

    row = n._process_single_ingredient_enhanced(
        {
            "name": "Arabinose",
            "standardName": "Arabinose",
            "category": "other",
            "ingredientGroup": "Arabinose",
            "quantity": None,
        },
        is_active=False,
    )
    assert row["canonical_id"] == "PII_ARABINOSE"
    assert row["canonical_source_db"] == "other_ingredients"


def test_normalizer_does_not_flag_true_unknown_as_recognized():
    n = EnhancedDSLDNormalizer()
    detail = n._build_unmapped_detail("Zzqx Unknown Botanical 999", [], is_active=True)
    assert not detail.get("recognized_non_identity")


def test_normalizer_marks_nested_display_only_unmapped_as_non_scoreable():
    n = EnhancedDSLDNormalizer()
    row = n._process_single_ingredient_enhanced(
        {
            "name": "B. lactis BS01",
            "standardName": "B. lactis BS01",
            "category": "bacteria",
            "ingredientGroup": "Bifidobacterium animalis lactis",
            "quantity": None,
            "unit": "NP",
            "parentBlend": "Probiotic Blend",
            "isNestedIngredient": True,
        },
        is_active=True,
    )

    assert row["cleaner_row_role"] == "nested_display_only"
    detail = n.unmapped_details["B. lactis BS01"]
    assert detail["non_scoreable_cleaner_row"] is True
    assert detail["cleaner_row_role"] == "nested_display_only"
    assert detail["score_exclusion_reason"] == "nested_display_only"


def test_unmapped_delta_counts_a_repeated_name_in_the_next_product():
    """A worker may process the same missing label in consecutive products."""
    normalizer = EnhancedDSLDNormalizer()
    normalizer._record_unmapped_ingredient(
        "Lactobacillus jensenii LBV 116",
        [],
        is_active=True,
        cleaner_row_role="nested_display_only",
        score_exclusion_reason="nested_display_only",
    )

    snapshot = normalizer.get_unmapped_snapshot()
    normalizer._record_unmapped_ingredient(
        "Lactobacillus jensenii LBV 116",
        [],
        is_active=True,
        cleaner_row_role="nested_display_only",
        score_exclusion_reason="nested_display_only",
    )

    delta = normalizer.get_unmapped_delta(snapshot)["unmapped"]
    assert len(delta) == 1
    assert delta[0]["name"] == "Lactobacillus jensenii LBV 116"
    assert delta[0]["occurrences"] == 1
    assert delta[0]["isActive"] is True


@pytest.mark.parametrize(
    ("label", "expected_canonical_id"),
    [
        ("Lactobacillus jensenii LBV 116", "lactobacillus_jensenii"),
        ("Black Mustard extract", "mustard_seed"),
        ("Agaricus blazei Whole Mushroom Extract", "royal_sun_blazei"),
        ("Coriolus versicolor Whole Mushroom Extract", "turkey_tail"),
        ("Maitake Whole Mushroom Extract", "maitake"),
        (
            "Boswellia serrata AKBA standardized extract (wood) resin",
            "boswellia",
        ),
    ],
)
def test_wave_one_nested_label_identity_aliases_resolve(
    label,
    expected_canonical_id,
):
    normalizer = EnhancedDSLDNormalizer()

    row = normalizer._process_single_ingredient_enhanced(
        {
            "name": label,
            "category": "botanical",
            "quantity": [{"quantity": 0, "unit": "NP"}],
            "parentBlend": "Wave One Blend",
            "isNestedIngredient": True,
        },
        is_active=True,
    )

    assert row["mapped"] is True
    assert row["canonical_id"] == expected_canonical_id
    assert row["canonical_source_db"] == "ingredient_quality_map"


def test_wave_one_single_declared_form_recovers_generic_nested_identity():
    normalizer = EnhancedDSLDNormalizer()

    row = normalizer._process_single_ingredient_enhanced(
        {
            "name": "Glycosides",
            "category": "non-nutrient/non-botanical",
            "quantity": [{"quantity": 0, "unit": "NP"}],
            "forms": [
                {
                    "name": "Polydatin",
                    "category": "non-nutrient/non-botanical",
                    "ingredientGroup": "Polydatin",
                }
            ],
            "ingredientGroup": "Polydatin",
            "parentBlend": "Resveratrol Complex",
            "isNestedIngredient": True,
        },
        is_active=True,
    )

    assert row["name"] == "Glycosides"
    assert row["mapped"] is True
    assert row["canonical_id"] == "resveratrol"
    assert row["canonical_source_db"] == "ingredient_quality_map"
    assert row["cleaner_row_role"] == "nested_display_only"
    assert row["score_eligible_by_cleaner"] is False
    assert row["forms"][0]["name"] == "Polydatin"


def test_wave_one_flaxseed_ala_context_beats_ambiguous_ala_alias():
    """ALA sourced from flaxseed in an omega blend is alpha-linolenic acid."""
    normalizer = EnhancedDSLDNormalizer()

    row = normalizer._process_single_ingredient_enhanced(
        {
            "name": "ALA",
            "category": "non-nutrient/non-botanical",
            "ingredientGroup": "Alpha Lipoic Acid",
            "quantity": [{"quantity": 50, "unit": "mg"}],
            "forms": [
                {
                    "name": "Flaxseed Oil",
                    "category": "fat",
                    "ingredientGroup": "Flaxseed Oil",
                }
            ],
            "parentBlend": "Omega Fatty Acid Blend",
            "isNestedIngredient": True,
        },
        is_active=True,
    )

    assert row["canonical_id"] == "alpha_linolenic_acid"
    assert row["standardName"] == "Alpha-Linolenic Acid"
    assert row["cleaner_match_method"] == "contextual_ala_identity"
    assert row["forms"][0]["name"] == "Flaxseed Oil"


def test_printed_nutrient_parent_beats_cross_parent_source_form_unii():
    """Sodium as sodium ascorbate remains the label nutrient Sodium."""
    normalizer = EnhancedDSLDNormalizer()

    row = normalizer._process_single_ingredient_enhanced(
        {
            "name": "Sodium",
            "category": "mineral",
            "ingredientGroup": "Sodium",
            "uniiCode": "9NEZ333N27",
            "quantity": [{"quantity": 5, "unit": "mg"}],
            "forms": [
                {
                    "name": "Sodium Ascorbate",
                    "category": "mineral",
                    "ingredientGroup": "Sodium",
                    "uniiCode": "S033EH8359",
                }
            ],
        },
        is_active=True,
    )

    assert row["canonical_id"] == "sodium"
    assert row["standardName"] == "Sodium"
    assert row["cleaner_match_method"] == "printed_nutrient_identity"
    assert row["forms"][0]["name"] == "Sodium Ascorbate"
