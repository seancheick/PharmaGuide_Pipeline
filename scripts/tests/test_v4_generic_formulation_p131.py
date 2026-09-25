"""Canonical generic Formulation contract.

Formulation owns form quality and formulation design. Dose, evidence,
ingredient count, focus, enzymes and consumer badges do not create points.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _ingredient(
    *,
    name: str = "Magnesium Bisglycinate",
    canonical_id: str = "magnesium_bisglycinate",
    bio_score: float | None = 14,
    quantity: float | None = 200,
    unit: str | None = "mg",
    **extra,
) -> dict:
    row = {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "mapped": bool(canonical_id),
        "source_section": "active",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
    }
    if bio_score is not None:
        row["bio_score"] = bio_score
    if quantity is not None:
        row["quantity"] = quantity
    if unit is not None:
        row["unit"] = unit
    row.update(extra)
    return row


def _product(*, ingredients: list[dict] | None = None, **extra) -> dict:
    rows = ingredients if ingredients is not None else [_ingredient()]
    product = {
        "status": "active",
        "form_factor": "capsule",
        "form_factor_canonical": "capsule",
        "supplement_taxonomy": {
            "primary_type": "general_supplement",
            "is_single_scorable_active": len(rows) == 1,
            "scorable_active_count": len(rows),
        },
        "ingredient_quality_data": {
            "total_active": len(rows),
            "ingredients_scorable": [r for r in rows if r.get("quantity")],
            "ingredients": rows,
        },
    }
    product.update(extra)
    return product


@pytest.mark.parametrize("bio_score,assessed", [(None, 0), (0.0, 1), (14.0, 1)])
def test_unrated_form_is_distinct_from_an_explicit_rating(bio_score, assessed) -> None:
    from scoring_v4.modules.generic_formulation import score_formulation
    from scoring_v4.quality_score import assemble_quality_score

    dim = score_formulation(_product(ingredients=[_ingredient(bio_score=bio_score)]))
    result = assemble_quality_score({
        "raw_score_v4_100": 0.0,
        "v4_verdict": "SAFE",
        "v4_module": "generic",
        "v4_breakdown": {"module": {"dimensions": {"formulation": dim}}},
    })

    assert dim["metadata"]["iqm_form_quality_assessed_count"] == assessed
    assert dim["components"]["A1_bio_score"] == (bio_score or 0.0)
    reason = result["quality_pillars_v4"]["formulation"]["reason"]
    assert ("not rated" in reason) is (bio_score is None)


def test_a1_is_equal_weight_mean_and_clamped() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    average = score_formulation(_product(ingredients=[
        _ingredient(name="A", canonical_id="a", bio_score=14),
        _ingredient(name="B", canonical_id="b", bio_score=10),
    ]))
    clamped = score_formulation(_product(ingredients=[_ingredient(bio_score=99)]))

    assert average["components"]["A1_bio_score"] == 12.0
    assert clamped["components"]["A1_bio_score"] == 15.0


def test_a1_uses_parent_relative_iqm_form_quality() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    # Riboflavin is tied for the best reviewed B2 form at IQM 10. Generic
    # Formulation must use the same within-parent scale as panel routes.
    result = score_formulation(_product(ingredients=[_ingredient(
        name="Riboflavin",
        canonical_id="vitamin_b2_riboflavin",
        bio_score=10,
    )]))

    assert result["components"]["A1_bio_score"] == 15.0


def test_a1_does_not_require_dose_disclosure() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    row = _ingredient(bio_score=12, quantity=None, unit=None)
    result = score_formulation(_product(ingredients=[row]))

    assert result["components"]["A1_bio_score"] == 12.0


def test_a1_skips_structural_rows_but_keeps_sole_mapped_blend() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    mixed = score_formulation(_product(ingredients=[
        _ingredient(name="Real", canonical_id="real", bio_score=14),
        _ingredient(name="Blend", canonical_id="blend", bio_score=2, is_proprietary_blend=True),
        _ingredient(name="Total", canonical_id="total", bio_score=2, is_parent_total=True),
    ]))
    sole_mapped = score_formulation(_product(ingredients=[
        _ingredient(name="Branded Complex", canonical_id="dim", bio_score=12, is_proprietary_blend=True),
    ]))
    sole_unmapped = score_formulation(_product(ingredients=[
        _ingredient(name="Mystery Blend", canonical_id="", bio_score=12, is_proprietary_blend=True),
    ]))

    assert mixed["components"]["A1_bio_score"] == 14.0
    assert sole_mapped["components"]["A1_bio_score"] == 12.0
    assert sole_unmapped["components"]["A1_bio_score"] == 0.0


def test_retired_generic_proxies_are_absent_and_cannot_move_score() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    base = _product()
    decorated = _product(
        formulation_data={
            "organic": {"usda_verified": True},
            "non_gmo": {"non_gmo_project_verified": True},
            "synergy_clusters": [{"match_count": 3, "evidence_tier": 1}],
        },
        natural_source_percentage=100,
    )
    result = score_formulation(decorated)
    retired = {
        "A2_premium_forms", "A5a_organic", "A5c_synergy_cluster",
        "A5d_non_gmo", "A5e_natural_source", "A6_single_ingredient",
        "enzyme_recognition", "premium_single_ingredient_floor_adjustment",
        "standard_single_ingredient_floor_adjustment",
    }

    assert result["score"] == score_formulation(base)["score"]
    assert retired.isdisjoint(result["components"])


@pytest.mark.parametrize("tier,expected", [(1, 3.0), (2, 2.0), (3, 1.0), (9, 0.0)])
def test_delivery_tiers(tier: int, expected: float) -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    result = score_formulation(_product(delivery_tier=tier))
    assert result["components"]["A3_delivery_system"] == expected


def test_absorption_pairing_has_one_owner() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    top = score_formulation(_product(absorption_enhancer_paired=True))
    nested = score_formulation(_product(absorption_data={"qualifies_for_bonus": True}))
    absent = score_formulation(_product(absorption_enhancer_paired=False))

    assert top["components"]["A4_absorption_enhancer"] == 3.0
    assert nested["components"]["A4_absorption_enhancer"] == 3.0
    assert absent["components"]["A4_absorption_enhancer"] == 0.0


@pytest.mark.parametrize(
    "evidence_source,expected",
    [("certificate", 1.0), ("marker_word_only", 0.5)],
)
def test_standardized_botanical_credit(evidence_source: str, expected: float) -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    result = score_formulation(_product(formulation_data={
        "standardized_botanicals": [{
            "meets_threshold": True,
            "evidence_source": evidence_source,
        }]
    }))
    assert result["components"]["A5b_standardized_botanical"] == expected


@pytest.mark.parametrize("level,expected", [("high", -4.0), ("moderate", -3.0)])
def test_dietary_sugar_penalty_bands(level: str, expected: float) -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    result = score_formulation(_product(dietary_sensitivity_data={
        "sugar": {"level": level},
        "sweeteners": {},
    }))
    assert result["penalties"]["B1_dietary_sugar"] == expected


def test_gummy_format_alone_has_no_formulation_penalty() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    capsule = score_formulation(_product())
    gummy = score_formulation(_product(form_factor="gummy", form_factor_canonical="gummy"))
    assert gummy["score"] == capsule["score"]


def test_watchlist_penalties_accumulate_and_fuzzy_does_not_charge() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    result = score_formulation(_product(contaminant_data={"banned_substances": {"substances": [
        {"status": "high_risk", "match_type": "exact"},
        {"status": "watchlist", "match_type": "alias"},
        {"status": "watchlist", "match_type": "fuzzy"},
    ]}}))
    assert result["penalties"]["B0_moderate_watchlist"] == -15.0


def test_harmful_additives_dedupe_by_rule_and_keep_applied_ledger() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    result = score_formulation(_product(contaminant_data={"harmful_additives": {"additives": [
        {"id": "ADD_X", "severity": "high", "source_section": "inactive", "ingredient": "X"},
        {"id": "ADD_X", "severity": "moderate", "source_section": "inactive", "ingredient": "X alias"},
    ]}}))
    assert result["penalties"]["B1_harmful_additives"] == -3.0
    assert result["metadata"]["inactive_penalty_details"][0]["matched_rule_id"] == "ADD_X"


def test_presence_floor_is_monotonic_and_cannot_hide_large_penalty() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    tiny = _product(ingredients=[_ingredient(bio_score=0.1)])
    tiny_penalized = _product(
        ingredients=[_ingredient(bio_score=0.1)],
        dietary_sensitivity_data={"sugar": {"level": "high"}},
    )
    strong_penalized = _product(
        ingredients=[_ingredient(bio_score=14)],
        contaminant_data={"banned_substances": {"substances": [
            {"status": "watchlist", "match_type": "exact"},
        ]}},
    )

    assert score_formulation(tiny)["score"] == 2.0
    assert score_formulation(tiny_penalized)["score"] == 2.0
    assert score_formulation(strong_penalized)["score"] == 9.0


def test_metadata_names_the_engine_and_contract_is_complete() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    result = score_formulation(_product())
    assert result["phase"] == "P1.3.1b_formulation_complete"
    assert result["metadata"]["formulation_profile"] == "generic_iqm"
    assert result["metadata"]["deferred_components"] == []
    assert result["max"] == 30.0


def test_empty_product_is_safe_and_zero() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    result = score_formulation({})
    assert result["score"] == 0.0
    assert result["components"]["A1_bio_score"] == 0.0


def test_generic_formulation_does_not_import_retired_scorer() -> None:
    import scoring_v4.modules.generic_formulation as module

    assert "score_supplements" not in inspect.getsource(module)
