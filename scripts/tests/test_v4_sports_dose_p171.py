"""Wave 6 sports v4 dose rubric tests."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules.sports_dose import score_dose
from scoring_v4.modules.sports_helpers import (
    dose_g,
    group_bcaa,
    group_eaa,
    primary_sports_identity,
    sports_rows,
)


def _row(
    canonical_id: str,
    quantity: float,
    unit: str,
    *,
    name: str | None = None,
    bio_score: float = 12.0,
) -> dict:
    return {
        "name": name or canonical_id.replace("_", " ").title(),
        "standard_name": name or canonical_id.replace("_", " ").title(),
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "bio_score": bio_score,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "dose_class": "therapeutic_mass",
        "source_section": "activeIngredients",
        "raw_source_path": f"activeIngredients[{canonical_id}]",
    }


def _product(*rows: dict, name: str = "Sports Product", primary_type: str = "amino_acid") -> dict:
    return {
        "fullName": name,
        "product_name": name,
        "primary_type": primary_type,
        "supplement_taxonomy": {"primary_type": primary_type},
        "ingredient_quality_data": {"ingredients_scorable": list(rows)},
    }


def test_dose_g_normalizes_grams_and_milligrams() -> None:
    assert dose_g(_row("creatine_monohydrate", 3, "Gram(s)")) == pytest.approx(3.0)
    assert dose_g(_row("creatine_monohydrate", 5000, "mg")) == pytest.approx(5.0)
    assert dose_g(_row("creatine_monohydrate", 5000000, "mcg")) == pytest.approx(5.0)


def test_sports_rows_filters_incidental_minerals() -> None:
    product = _product(
        _row("calcium", 200, "mg"),
        _row("vitamin_d", 20, "mcg"),
        _row("creatine_monohydrate", 5, "Gram(s)"),
    )

    assert [row["canonical_id"] for row in sports_rows(product)] == ["creatine_monohydrate"]


def test_group_bcaa_totals_ratio_and_components() -> None:
    product = _product(
        _row("l_leucine", 5, "Gram(s)"),
        _row("l_isoleucine", 2.5, "Gram(s)"),
        _row("l_valine", 2.5, "Gram(s)"),
    )

    grouped = group_bcaa(sports_rows(product))

    assert grouped["complete"] is True
    assert grouped["total_g"] == pytest.approx(10.0)
    assert grouped["ratio"] == pytest.approx((2.0, 1.0, 1.0))


def test_group_eaa_requires_at_least_six_essential_amino_acids() -> None:
    product = _product(
        _row("l_histidine", 500, "mg"),
        _row("l_isoleucine", 500, "mg"),
        _row("l_leucine", 1000, "mg"),
        _row("l_lysine", 500, "mg"),
        _row("l_phenylalanine", 500, "mg"),
        _row("l_threonine", 500, "mg"),
    )

    grouped = group_eaa(sports_rows(product))

    assert grouped["complete"] is True
    assert grouped["count"] == 6
    assert grouped["total_g"] == pytest.approx(3.5)


def test_primary_identity_prefers_creatine_single() -> None:
    product = _product(_row("creatine_monohydrate", 3, "Gram(s)"), name="Creatine Monohydrate")

    assert primary_sports_identity(product) == "creatine"


def test_creatine_three_grams_is_evaluable_partial_high_credit() -> None:
    payload = score_dose(_product(_row("creatine_monohydrate", 3, "Gram(s)"), name="Creatine Monohydrate"))

    assert payload["score"] == pytest.approx(16.0)
    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(16.0)
    assert payload["metadata"]["primary_identity"] == "creatine"
    assert payload["metadata"]["dose_basis"] == "creatine_3_to_5_g"


def test_creatine_five_grams_scores_primary_dose_max() -> None:
    payload = score_dose(_product(_row("creatine_monohydrate", 5000, "mg"), name="Creatine Monohydrate"))

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(20.0)
    assert payload["score"] == pytest.approx(20.0)


def test_whey_twenty_two_grams_uses_protein_serving_not_minerals() -> None:
    payload = score_dose(
        _product(
            _row("calcium", 25, "mg"),
            _row("iron", 1, "mg"),
            _row("whey_protein", 22.5, "Gram(s)", name="Whey Protein Isolate"),
            name="Whey Protein Isolate",
            primary_type="protein_powder",
        )
    )

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(20.0)
    assert payload["metadata"]["primary_identity"] == "protein"
    assert payload["metadata"]["dose_basis"] == "protein_20_to_40_g"


def test_beta_alanine_three_point_two_grams_scores_below_max_band() -> None:
    payload = score_dose(_product(_row("beta-alanine", 3200, "mg"), name="Beta-Alanine"))

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(16.0)
    assert payload["metadata"]["primary_identity"] == "beta_alanine"


def test_citrulline_malate_six_grams_is_conservative_partial_credit() -> None:
    payload = score_dose(_product(_row("l_citrulline", 6000, "mg", name="L-Citrulline Malate"), name="Citrulline Malate"))

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(14.0)
    assert payload["metadata"]["primary_identity"] == "citrulline"
    assert payload["metadata"]["dose_basis"] == "citrulline_malate_6_to_8_g"


def test_bcaa_2_1_1_ratio_scores_high_with_completeness_credit() -> None:
    payload = score_dose(
        _product(
            _row("l_leucine", 5, "Gram(s)"),
            _row("l_isoleucine", 2.5, "Gram(s)"),
            _row("l_valine", 2.5, "Gram(s)"),
            name="Precision BCAA",
        )
    )

    assert payload["components"]["sports_primary_active_dose"] == pytest.approx(18.0)
    assert payload["components"]["sports_ratio_or_completeness"] == pytest.approx(2.0)
    assert payload["score"] == pytest.approx(20.0)
    assert payload["metadata"]["primary_identity"] == "bcaa"


def test_opaque_preworkout_without_sports_dose_is_not_evaluable_with_penalty() -> None:
    product = {
        "fullName": "Pre-Workout Elite",
        "product_name": "Pre-Workout Elite",
        "primary_type": "pre_workout",
        "supplement_taxonomy": {"primary_type": "pre_workout"},
        "ingredient_quality_data": {"ingredients_scorable": []},
        "proprietary_blends": [{"name": "Performance Blend", "disclosure_level": "none"}],
    }

    payload = score_dose(product)

    assert payload["score"] == 0.0
    assert payload["penalties"]["opaque_primary_sports_blend"] == pytest.approx(-10.0)
    assert payload["metadata"]["not_evaluable_reason"] == "opaque_primary_sports_blend"
