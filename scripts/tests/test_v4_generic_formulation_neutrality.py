"""Count- and dose-neutral contracts for the generic Formulation pillar."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _row(index: int, *, bio: float = 14.0, dose: bool = True) -> dict:
    row = {
        "name": f"Active {index}",
        "standard_name": f"Active {index}",
        "canonical_id": f"active_{index}",
        "bio_score": bio,
        "mapped": True,
        "mapped_identity": True,
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "raw_source_path": f"ingredientRows[{index}]",
    }
    if dose:
        row.update(quantity=100.0, unit="mg", has_dose=True)
    else:
        row.update(
            quantity=0.0,
            unit="NP",
            has_dose=False,
            score_eligible_by_cleaner=False,
            identity_decision_reason="no_dose_evidence",
            score_exclusion_reason="recognized_non_scorable",
        )
    return row


def _product(count: int, *, bio: float = 14.0, dose: bool = True) -> dict:
    rows = [_row(index, bio=bio, dose=dose) for index in range(count)]
    return {
        "product_name": "Neutrality fixture",
        "supplement_taxonomy": {
            "primary_type": "general_supplement",
            "is_single_scorable_active": count == 1,
            "scorable_active_count": count,
        },
        "ingredient_quality_data": {
            "ingredients": rows,
            "ingredients_scorable": rows if dose else [],
            "total_active": count,
        },
    }


_IMMUNE_ROWS = (
    ("Vitamin C", "vitamin_c", 500.0, "mg"),
    ("Vitamin D3", "vitamin_d3", 25.0, "mcg"),
    ("Zinc", "zinc", 15.0, "mg"),
    ("Copper", "copper", 1.0, "mg"),
    ("Selenium", "selenium", 55.0, "mcg"),
    ("Beta glucan", "beta_glucan", 250.0, "mg"),
    ("Quercetin", "quercetin", 500.0, "mg"),
    ("Elderberry", "elderberry", 300.0, "mg"),
)


def _immune_product(count: int, *, disclosed_count: int | None = None) -> dict:
    disclosed = count if disclosed_count is None else disclosed_count
    rows = []
    for index, (name, canonical_id, quantity, unit) in enumerate(
        _IMMUNE_ROWS[:count]
    ):
        row = _row(index, bio=14.0, dose=index < disclosed)
        row.update(
            name=name,
            standard_name=name,
            canonical_id=canonical_id,
        )
        if index < disclosed:
            row.update(quantity=quantity, unit=unit, has_dose=True)
        rows.append(row)
    return {
        "product_name": "Immune formulation neutrality fixture",
        "supplement_taxonomy": {
            "primary_type": "immune_support",
            "is_single_scorable_active": count == 1,
            "scorable_active_count": disclosed,
        },
        "ingredient_quality_data": {
            "ingredients": rows,
            "ingredients_scorable": rows[:disclosed],
            "total_active": count,
        },
    }


def test_equal_form_quality_is_neutral_to_ingredient_count() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    scores = [score_formulation(_product(count))["score"] for count in (1, 2, 3, 8)]

    assert scores == [14.0, 14.0, 14.0, 14.0]


def test_disclosing_or_omitting_dose_does_not_change_form_quality() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    disclosed = score_formulation(_product(1, bio=12.0, dose=True))
    undisclosed = score_formulation(_product(1, bio=12.0, dose=False))

    assert disclosed["components"]["A1_bio_score"] == 12.0
    assert undisclosed["components"]["A1_bio_score"] == 12.0
    assert disclosed["score"] == undisclosed["score"] == 12.0


def test_immune_formulation_is_neutral_to_recognized_ingredient_count() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    results = [score_formulation(_immune_product(count)) for count in (1, 3, 5, 8)]

    assert [result["score"] for result in results] == [14.0] * 4
    assert all("immune_support_profile" not in result["components"] for result in results)


def test_undisclosed_immune_rows_cannot_manufacture_formulation_credit() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    one_disclosed = score_formulation(_immune_product(1))
    seven_undisclosed = score_formulation(
        _immune_product(8, disclosed_count=1)
    )

    assert seven_undisclosed["score"] == one_disclosed["score"] == 14.0
    assert "immune_support_profile" not in seven_undisclosed["components"]


def test_dose_gated_synergy_does_not_change_formulation() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    base = _product(2, bio=12.0)
    qualified = _product(2, bio=12.0)
    qualified["formulation_data"] = {
        "synergy_clusters": [{
            "match_count": 2,
            "evidence_tier": 1,
            "matched_ingredients": [
                {"min_effective_dose": 100, "meets_minimum": True},
                {"min_effective_dose": 100, "meets_minimum": True},
            ],
        }]
    }

    assert score_formulation(qualified)["score"] == score_formulation(base)["score"]


def test_single_product_floor_cannot_hide_a_watchlist_penalty() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(1, bio=14.0)
    product["supplement_taxonomy"]["primary_type"] = "single_botanical"
    product["contaminant_data"] = {
        "banned_substances": {
            "substances": [{
                "id": "fixture-watchlist",
                "status": "watchlist",
                "match_type": "exact",
            }]
        }
    }

    result = score_formulation(product)

    assert result["penalties"]["B0_moderate_watchlist"] == -5.0
    assert result["score"] == 9.0
    assert "premium_single_ingredient_floor_adjustment" not in result["components"]
    assert "standard_single_ingredient_floor_adjustment" not in result["components"]


def test_formulation_reference_follows_engine_not_product_archetype() -> None:
    from scoring_v4.quality_score import _config, _pillar_formulation

    cfg = _config()
    generic = _pillar_formulation(
        {"score": 15.0, "metadata": {"formulation_profile": "generic_iqm"}},
        20.0,
        "sports_single",
        cfg,
    )
    botanical = _pillar_formulation(
        {"score": 15.0, "metadata": {"formulation_profile": "botanical"}},
        20.0,
        "generic_botanical_branded",
        cfg,
    )
    dedicated_sports = _pillar_formulation(
        {"score": 24.0, "metadata": {}},
        20.0,
        "sports_single",
        cfg,
    )

    assert generic["score"] == 20.0
    assert generic["components"]["reference"] == 15.0
    assert botanical["score"] == 20.0
    assert botanical["components"]["reference"] == 15.0
    assert dedicated_sports["score"] == 20.0
    assert dedicated_sports["components"]["reference"] == 24.0
