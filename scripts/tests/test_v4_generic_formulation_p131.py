"""v4 Generic Formulation dimension — P1.3.1 tests.

Covers the 8 simple sub-rubrics implemented in this slice:
  A1 bio_score, A2 premium forms, A3 delivery, A4 absorption,
  A5a organic, A5e natural source, A6 single-ingredient,
  B1 dietary sugar penalty.

P1.3.1b extends the same dimension with A5b standardized botanical,
A5c synergy 4-tier, A5d non-GMO, enzyme recognition, B0 moderate /
watchlist, and B1 harmful-additive penalties.

Tests target the module API (`score_formulation`) directly AND verify
the v4 scorer wires the dimension score through.
"""

from __future__ import annotations

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
    natural: bool = False,
    is_proprietary_blend: bool = False,
    is_parent_total: bool = False,
    **extra,
) -> dict:
    row = {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "mapped": bool(canonical_id),
        "is_proprietary_blend": is_proprietary_blend,
        "is_parent_total": is_parent_total,
        "natural": natural,
    }
    if bio_score is not None:
        row["bio_score"] = bio_score
    if quantity is not None:
        row["quantity"] = quantity
    if unit is not None:
        row["unit"] = unit
    row.update(extra)
    return row


def _product(
    *,
    supp_type: str = "single_nutrient",
    ingredients: list | None = None,
    **extra,
) -> dict:
    rows = ingredients if ingredients is not None else [_ingredient()]
    product = {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": supp_type},
        "ingredient_quality_data": {
            "total_active": len(rows),
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
    }
    product.update(extra)
    return product


# --- A1 bio_score ---------------------------------------------------------


def test_a1_bio_score_avg_across_scorable_actives() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        ingredients=[
            _ingredient(name="A", bio_score=14),
            _ingredient(name="B", bio_score=10),
        ]
    )
    payload = score_formulation(product)

    assert payload["components"]["A1_bio_score"] == 12.0


def test_a1_bio_score_skips_proprietary_blend_and_parent_total() -> None:
    """v3 dose-anchored separation: proprietary-blend containers and
    parent-total roll-ups don't contribute to bio_score average."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        ingredients=[
            _ingredient(name="Real Active", bio_score=14),
            _ingredient(name="Proprietary Container", bio_score=2, is_proprietary_blend=True),
            _ingredient(name="Parent Total Row", bio_score=2, is_parent_total=True),
        ]
    )
    payload = score_formulation(product)
    assert payload["components"]["A1_bio_score"] == 14.0


def test_a1_bio_score_includes_sole_mapped_proprietary_blend_parent() -> None:
    """v3 exemption: a mapped proprietary/blend row is scoreable for A1
    when it is the only dose-bearing active. This protects legitimate
    single-row branded actives like I3C/DIM Complex or BioCell Collagen."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        ingredients=[
            _ingredient(
                name="I3C/DIM Complex",
                canonical_id="dim",
                bio_score=12,
                is_proprietary_blend=True,
            )
        ]
    )
    payload = score_formulation(product)

    assert payload["components"]["A1_bio_score"] == 12.0


def test_a1_bio_score_skips_unmapped_sole_proprietary_blend_parent() -> None:
    """Opaque marketing blends without a mapped IQM identity still earn
    no A1 credit even when they are the only active row."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        ingredients=[
            _ingredient(
                name="Proprietary Blend",
                canonical_id="",
                bio_score=12,
                is_proprietary_blend=True,
            )
        ]
    )
    payload = score_formulation(product)

    assert payload["components"]["A1_bio_score"] == 0.0


def test_a1_bio_score_zero_when_no_scorable_ingredient() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(ingredients=[_ingredient(quantity=None, unit=None, bio_score=14)])
    payload = score_formulation(product)
    assert payload["components"]["A1_bio_score"] == 0.0


def test_a1_bio_score_clamps_to_15() -> None:
    """Even with anomalously high enriched bio_scores, the dimension
    contribution clamps at CAP_BIO_SCORE = 15."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(ingredients=[_ingredient(bio_score=99)])
    payload = score_formulation(product)
    assert payload["components"]["A1_bio_score"] == 15.0


# --- A2 premium forms -----------------------------------------------------


def test_a2_premium_forms_skip_first_single_premium() -> None:
    """One premium form alone earns 0 (skip-first rule)."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(ingredients=[_ingredient(bio_score=14)])
    payload = score_formulation(product)
    assert payload["components"]["A2_premium_forms"] == 0.0


def test_a2_premium_forms_two_premium_forms_yields_half_point() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        ingredients=[
            _ingredient(name="Mg Glycinate", canonical_id="mg_glycinate", bio_score=14),
            _ingredient(name="Mg Malate", canonical_id="mg_malate", bio_score=13),
        ]
    )
    payload = score_formulation(product)
    assert payload["components"]["A2_premium_forms"] == 0.5


def test_a2_premium_forms_below_threshold_doesnt_count() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        ingredients=[
            _ingredient(canonical_id="a", bio_score=14),
            _ingredient(canonical_id="b", bio_score=11),  # below threshold 12
        ]
    )
    payload = score_formulation(product)
    assert payload["components"]["A2_premium_forms"] == 0.0


def test_a2_premium_forms_caps_at_4() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    rows = [_ingredient(canonical_id=f"prem_{i}", bio_score=14) for i in range(20)]
    product = _product(ingredients=rows)
    payload = score_formulation(product)
    assert payload["components"]["A2_premium_forms"] == 4.0


def test_a2_premium_forms_does_not_use_sole_blend_parent_exemption() -> None:
    """The sole mapped blend-parent exemption is A1-only. v3 A2 skips
    proprietary containers even when they are mapped and dose-bearing."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        ingredients=[
            _ingredient(
                name="I3C/DIM Complex",
                canonical_id="dim",
                bio_score=14,
                is_proprietary_blend=True,
            )
        ]
    )
    payload = score_formulation(product)

    assert payload["components"]["A1_bio_score"] == 14.0


def test_presence_floor_preserves_positive_form_signal_after_penalty_clamp() -> None:
    """A harmful-additive penalty should not erase the separate fact that a
    mapped active has some form-quality signal."""
    from scoring_v4.modules.generic_formulation import FORMULATION_PRESENCE_FLOOR, score_formulation

    product = _product(
        supp_type="multi",
        ingredients=[
            _ingredient(
                name="Magnesium Oxide",
                canonical_id="magnesium_oxide",
                bio_score=3,
            )
        ],
        contaminant_data={
            "harmful_additives": {
                "additives": [
                    {"additive_id": "one", "severity_level": "critical"},
                    {"additive_id": "two", "severity_level": "high"},
                ]
            }
        },
    )

    payload = score_formulation(product)

    assert payload["score"] == FORMULATION_PRESENCE_FLOOR
    assert payload["metadata"]["presence_floor"]["applied"] is True
    assert payload["metadata"]["presence_floor"]["pre_floor_score"] < 0


def test_presence_floor_does_not_apply_without_mapped_active() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        ingredients=[
            _ingredient(
                name="Unknown Active",
                canonical_id="",
                bio_score=None,
                quantity=None,
            )
        ],
        contaminant_data={
            "harmful_additives": {
                "additives": [{"additive_id": "one", "severity_level": "critical"}]
            }
        },
    )

    payload = score_formulation(product)

    assert payload["score"] == 0.0
    assert payload["metadata"]["presence_floor"]["applied"] is False
    assert payload["components"]["A2_premium_forms"] == 0.0


def test_presence_floor_does_not_apply_to_product_level_evidence_without_cleaner_active() -> None:
    """Product-level evidence can support dose/blend scoring, but it should not
    satisfy the formulation presence floor unless the cleaner promoted a real
    scorable active row."""
    from scoring_v4.modules.generic_formulation import score_formulation

    evidence_base = {
        "evidence_type": "blend_anchor_mass",
        "scoreable": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "source": "active",
        "evidence_scope": "blend_level",
        "evidence_origin": "compatibility_derived",
        "linked_rows": ["ingredientRows[0]"],
        "confidence": "medium",
        "reason": "identity_bearing_blend_header_mass",
        "canonical_id": "phytosterols",
        "clean_identity_id": "phytosterols",
        "scoring_parent_id": "phytosterols",
        "evidence_canonical_id": "phytosterols",
        "canonical_source_db": "ingredient_quality_map",
        "raw_taxonomy": {
            "category": "blend",
            "ingredientGroup": "Blend (Fatty Acid or Fat/Oil Supplement)",
            "forms": [{"name": "Pine", "category": "botanical"}],
        },
        "anchor_risk_class": "botanical_or_standardized",
    }
    product = _product(
        supp_type="targeted",
        ingredients=[],
        product_name="Moducare",
        product_scoring_evidence=[
            {
                **evidence_base,
                "name": "Sterols",
                "raw_source_path": "ingredientRows[0]",
                "dose_value": 20.0,
                "dose_unit": "mg",
                "raw_source_text": "Sterols",
            },
            {
                **evidence_base,
                "name": "Sterolins",
                "raw_source_path": "ingredientRows[1]",
                "dose_value": 200.0,
                "dose_unit": "mcg",
                "raw_source_text": "Sterolins",
                "linked_rows": ["ingredientRows[1]"],
            },
        ],
        contaminant_data={
            "harmful_additives": {
                "additives": [{"additive_id": "one", "severity_level": "moderate"}]
            }
        },
    )

    payload = score_formulation(product)

    assert payload["components"]["A5e_natural_source"] == 1.0
    assert payload["metadata"]["botanical_formulation"]["weak_or_unidentified_botanical"] == -4.0
    assert payload["score"] == 0.0
    assert payload["metadata"]["presence_floor"]["applied"] is False


# --- A3 delivery system ---------------------------------------------------


def test_a3_delivery_tier_1_returns_3() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(delivery_tier=1)
    payload = score_formulation(product)
    assert payload["components"]["A3_delivery_system"] == 3.0


def test_a3_delivery_tier_2_returns_2() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(delivery_tier=2)
    payload = score_formulation(product)
    assert payload["components"]["A3_delivery_system"] == 2.0


def test_a3_delivery_tier_3_returns_1() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(delivery_tier=3)
    payload = score_formulation(product)
    assert payload["components"]["A3_delivery_system"] == 1.0


def test_a3_delivery_tier_via_delivery_data_fallback() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(delivery_data={"highest_tier": 1})
    payload = score_formulation(product)
    assert payload["components"]["A3_delivery_system"] == 3.0


def test_a3_delivery_unknown_tier_returns_zero() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product()  # no delivery_tier field
    payload = score_formulation(product)
    assert payload["components"]["A3_delivery_system"] == 0.0


# --- A4 absorption enhancer ----------------------------------------------


def test_a4_absorption_paired_top_level() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(absorption_enhancer_paired=True)
    payload = score_formulation(product)
    assert payload["components"]["A4_absorption_enhancer"] == 3.0


def test_a4_absorption_qualifies_via_absorption_data() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(absorption_data={"qualifies_for_bonus": True})
    payload = score_formulation(product)
    assert payload["components"]["A4_absorption_enhancer"] == 3.0


def test_a4_absorption_paired_false_returns_zero() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(absorption_enhancer_paired=False)
    payload = score_formulation(product)
    assert payload["components"]["A4_absorption_enhancer"] == 0.0


# --- A5a organic ----------------------------------------------------------


def test_a5a_organic_usda_verified() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(formulation_data={"organic": {"usda_verified": True}})
    payload = score_formulation(product)
    assert payload["components"]["A5a_organic"] == 1.0


def test_a5a_organic_claimed_without_exclusion() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        formulation_data={"organic": {"claimed": True, "exclusion_matched": False}}
    )
    payload = score_formulation(product)
    assert payload["components"]["A5a_organic"] == 1.0


def test_a5a_organic_claimed_with_exclusion_skipped() -> None:
    """A claim that the exclusion-matcher rejected (e.g. 'organic-shaped'
    marketing on a product that doesn't qualify) earns 0."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        formulation_data={"organic": {"claimed": True, "exclusion_matched": True}}
    )
    payload = score_formulation(product)
    assert payload["components"]["A5a_organic"] == 0.0


# --- A5e natural source ---------------------------------------------------


def test_a5e_natural_source_majority_natural() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        ingredients=[
            _ingredient(canonical_id="a", natural=True),
            _ingredient(canonical_id="b", natural=True),
            _ingredient(canonical_id="c", natural=False),
        ]
    )
    payload = score_formulation(product)
    assert payload["components"]["A5e_natural_source"] == 1.0


def test_a5e_natural_source_minority_natural_returns_zero() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        ingredients=[
            _ingredient(canonical_id="a", natural=False),
            _ingredient(canonical_id="b", natural=False),
            _ingredient(canonical_id="c", natural=True),
        ]
    )
    payload = score_formulation(product)
    assert payload["components"]["A5e_natural_source"] == 0.0


# --- A6 single-ingredient efficiency --------------------------------------


def test_a6_single_ingredient_efficiency_high_bio_single_type() -> None:
    """v4.1 tiered A6: elite form (bio >= 14) earns the top tier (+4),
    compensating focused singles for the A2 breadth bonus they cannot earn."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=14)])
    payload = score_formulation(product)
    assert payload["components"]["A6_single_ingredient"] == 4.0


def test_a6_tier_solid_premium_bio_12() -> None:
    """v4.1 tiered A6: solid-premium form (bio 12-13) earns +3."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=12)])
    payload = score_formulation(product)
    assert payload["components"]["A6_single_ingredient"] == 3.0


def test_a6_tier_good_bio_10() -> None:
    """v4.1 tiered A6: good form (bio 10-11) earns +1."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=10)])
    payload = score_formulation(product)
    assert payload["components"]["A6_single_ingredient"] == 1.0


def test_a6_single_ingredient_skipped_for_non_single_supp_type() -> None:
    """A6 stays mutually exclusive with A2: a multi earns A2 breadth, never A6."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="multivitamin", ingredients=[_ingredient(bio_score=14)])
    payload = score_formulation(product)
    assert payload["components"]["A6_single_ingredient"] == 0.0


def test_a6_single_ingredient_requires_exactly_one_scorable_active() -> None:
    """D3 + K2 style products may route as single_nutrient, but they are
    not focused single-active labels and must not earn A6."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        supp_type="single_nutrient",
        ingredients=[
            _ingredient(
                name="Vitamin D3",
                canonical_id="vitamin_d",
                bio_score=14,
                quantity=125,
                unit="mcg",
            ),
            _ingredient(
                name="Vitamin K2",
                canonical_id="vitamin_k",
                bio_score=14,
                quantity=50,
                unit="mcg",
            ),
        ],
    )
    payload = score_formulation(product)
    assert payload["components"]["A6_single_ingredient"] == 0.0


def test_a6_single_ingredient_below_floor_returns_zero() -> None:
    """Below the bio-10 floor (acceptable/weak form) earns nothing."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=9)])
    payload = score_formulation(product)
    assert payload["components"]["A6_single_ingredient"] == 0.0


def test_premium_single_formulation_floor_lifts_elite_focused_single() -> None:
    """An elite focused single can reach a premium formulation tier even though
    it cannot earn multi-form breadth credit."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=14)])
    payload = score_formulation(product)

    assert payload["score"] == 24.0
    assert payload["components"]["premium_single_ingredient_floor_adjustment"] == 6.0
    assert payload["metadata"]["premium_single_ingredient_floor"]["target"] == 24.0


def test_premium_single_formulation_floor_lifts_solid_focused_single_less() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=12)])
    payload = score_formulation(product)

    assert payload["score"] == 22.0
    assert payload["components"]["premium_single_ingredient_floor_adjustment"] == 7.0
    assert payload["metadata"]["premium_single_ingredient_floor"]["target"] == 22.0


def test_premium_single_formulation_floor_does_not_lift_weak_single() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=10)])
    payload = score_formulation(product)

    assert "premium_single_ingredient_floor_adjustment" not in payload["components"]
    assert payload["score"] == 11.0


def test_standard_single_formulation_floor_lifts_validated_low_bio_simple_molecule() -> None:
    """NAC has poor oral bioavailability, but standard oral NAC is still the
    clinically validated supplement form. A focused NAC product should not be
    treated like a weak formulation solely because no premium form exists.
    """
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        supp_type="single_nutrient",
        ingredients=[
            _ingredient(
                name="N-Acetyl Cysteine",
                canonical_id="nac",
                bio_score=6,
                quantity=600,
                unit="mg",
            )
        ],
    )
    payload = score_formulation(product)

    assert payload["score"] == 13.0
    assert payload["components"]["standard_single_ingredient_floor_adjustment"] == 7.0
    assert payload["metadata"]["standard_single_ingredient_floor"]["target"] == 13.0
    assert payload["metadata"]["premium_single_ingredient_floor"]["target"] == 0.0


def test_standard_single_formulation_floor_does_not_lift_unknown_low_bio_single() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        supp_type="single_nutrient",
        ingredients=[_ingredient(name="Unknown Low Bio", canonical_id="unknown_low_bio", bio_score=6)],
    )
    payload = score_formulation(product)

    assert payload["score"] == 6.0
    assert "standard_single_ingredient_floor_adjustment" not in payload["components"]
    assert payload["metadata"]["standard_single_ingredient_floor"]["target"] == 0.0


def test_premium_single_formulation_floor_does_not_lift_multi() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="multivitamin", ingredients=[_ingredient(bio_score=14)])
    payload = score_formulation(product)

    assert "premium_single_ingredient_floor_adjustment" not in payload["components"]
    assert payload["score"] == 14.0


def test_premium_single_formulation_floor_does_not_lift_proprietary_container() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        supp_type="single_nutrient",
        ingredients=[
            _ingredient(
                bio_score=14,
                is_proprietary_blend=True,
            )
        ],
    )
    payload = score_formulation(product)

    assert "premium_single_ingredient_floor_adjustment" not in payload["components"]


# --- A6 reads EFFECTIVE A1-slot quality (botanical/collagen seam fix) ------
# A6 was reading the raw row bio_score, so botanical singles (Meriva/Curcumin
# Phytosome, KSM-66) earned 0 even though the botanical adapter recognized a
# premium profile in the A1 slot. The fix: A6 evaluates whatever fills the A1
# slot (bio for generic, adapter for botanical/collagen) — one brain.


def test_a6_tier_function_reads_effective_quality_not_raw_bio() -> None:
    """The tier function scores the EFFECTIVE quality passed in, divorced from
    the raw row bio_score (here a deliberately-low 2.0)."""
    from scoring_v4.modules.generic_formulation import (
        _score_single_ingredient_efficiency as a6,
    )

    single = _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=2)])
    assert a6(single, 15.0) == 4.0
    assert a6(single, 12.0) == 3.0
    assert a6(single, 10.0) == 1.0
    assert a6(single, 9.0) == 0.0
    assert a6(single, None) == 0.0


def test_a6_tier_function_gate_blocks_non_single() -> None:
    from scoring_v4.modules.generic_formulation import (
        _score_single_ingredient_efficiency as a6,
    )

    multi = _product(supp_type="multivitamin", ingredients=[_ingredient(bio_score=2)])
    assert a6(multi, 15.0) == 0.0


def _botanical_single(**ing_overrides) -> dict:
    row = {
        "name": "Curcumin Phytosome",
        "standard_name": "Curcumin",
        "canonical_id": "curcumin",
        "mapped": True,
        "quantity": 500,
        "unit": "mg",
        "bio_score": 8.0,  # herbs sit low on the vitamin/mineral bio scale
        "raw_taxonomy": {"category": "botanical", "ingredientGroup": "Curcumin"},
    }
    row.update(ing_overrides)
    return _product(supp_type="single_nutrient", ingredients=[row])


def test_a6_botanical_single_earns_focus_from_adapter_not_raw_bio() -> None:
    """Premium botanical single: raw bio is 8, but the botanical adapter fills
    the A1 slot with a premium score, so A6 must fire (was silently 0)."""
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(_botanical_single())
    a1 = payload["components"]["A1_bio_score"]
    a6 = payload["components"]["A6_single_ingredient"]
    assert a1 >= 10.0  # adapter recognized the botanical (not the raw bio 8)
    assert a6 >= 1.0   # BUG FIX: previously 0 because A6 read raw bio 8
    # one-brain invariant: A6 reflects the effective A1-slot tier
    expected = 4.0 if a1 >= 14 else 3.0 if a1 >= 12 else 1.0 if a1 >= 10 else 0.0
    assert a6 == expected


def test_a6_one_brain_invariant_holds_for_generic_single() -> None:
    """For a generic single the effective A1 slot IS the bio average, so the
    pre-existing bio-tier behavior is preserved (no regression)."""
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=14)])
    )
    a1 = payload["components"]["A1_bio_score"]
    a6 = payload["components"]["A6_single_ingredient"]
    expected = 4.0 if a1 >= 14 else 3.0 if a1 >= 12 else 1.0 if a1 >= 10 else 0.0
    assert a6 == expected == 4.0


def test_a6_single_ingredient_does_not_use_sole_blend_parent_exemption() -> None:
    """Keep A6 aligned with v3: proprietary containers do not earn the
    single-ingredient efficiency bonus."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        supp_type="single_nutrient",
        ingredients=[
            _ingredient(
                name="I3C/DIM Complex",
                canonical_id="dim",
                bio_score=14,
                is_proprietary_blend=True,
            )
        ],
    )
    payload = score_formulation(product)

    assert payload["components"]["A1_bio_score"] == 14.0
    assert payload["components"]["A6_single_ingredient"] == 0.0


# --- Dose-unit parity with v3 ---------------------------------------------


def test_dfe_units_are_dose_eligible_for_formulation_quality() -> None:
    """v3 accepts FDA Dietary Folate Equivalent units; v4 must not zero
    folate form quality just because the unit is `mcg DFE` / `mcgdfe`."""
    from scoring_v4.modules.generic_formulation import score_formulation

    ing = _ingredient(
        name="Folate",
        canonical_id="folate",
        bio_score=13,
        quantity=400,
        unit="mcg DFE",
    )
    ing["unit_normalized"] = "mcgdfe"
    product = _product(ingredients=[ing])
    payload = score_formulation(product)

    assert payload["components"]["A1_bio_score"] == 13.0


def test_live_cell_units_are_dose_eligible_for_formulation_quality() -> None:
    """v3 accepts live/viable cell unit labels as dose-bearing probiotic
    equivalents. Generic helper parity matters for shared future modules."""
    from scoring_v4.modules.generic_formulation import score_formulation

    ing = _ingredient(
        name="Lactobacillus rhamnosus",
        canonical_id="lactobacillus_rhamnosus",
        bio_score=12,
        quantity=20,
        unit="live cell(s)",
    )
    product = _product(ingredients=[ing])
    payload = score_formulation(product)

    assert payload["components"]["A1_bio_score"] == 12.0


def test_greek_mu_microgram_unit_is_dose_eligible_alias() -> None:
    """Accept both common microgram glyphs: `µg` (micro sign, v3) and
    `μg` (Greek mu, label/OCR variant). This is a spelling alias, not a
    new dose-unit policy."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(ingredients=[_ingredient(bio_score=12, quantity=100, unit="μg")])
    payload = score_formulation(product)

    assert payload["components"]["A1_bio_score"] == 12.0


def test_ml_unit_is_not_dose_eligible_for_formulation_quality() -> None:
    """v3 does not accept volume-only liquid amounts for A1 form quality.
    Keep v4 parity until a documented dose-policy change lands."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(ingredients=[_ingredient(bio_score=12, quantity=5, unit="ml")])
    payload = score_formulation(product)

    assert payload["components"]["A1_bio_score"] == 0.0


def test_percent_unit_is_not_dose_eligible_for_formulation_quality() -> None:
    """A standardized-extract percent alone is not a dose amount. A5b can
    credit standardization separately; A1 still needs a v3-recognized dose."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(ingredients=[_ingredient(bio_score=12, quantity=95, unit="%")])
    payload = score_formulation(product)

    assert payload["components"]["A1_bio_score"] == 0.0


# --- B1 dietary sugar penalty ---------------------------------------------


def test_b1_dietary_sugar_high_penalty_4() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(dietary_sensitivity_data={"sugar": {"level": "high"}})
    payload = score_formulation(product)
    assert payload["penalties"]["B1_dietary_sugar"] == -4.0


def test_b1_dietary_sugar_moderate_penalty_3() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(dietary_sensitivity_data={"sugar": {"level": "moderate"}})
    payload = score_formulation(product)
    assert payload["penalties"]["B1_dietary_sugar"] == -3.0


def test_b1_dietary_sugar_low_added_source_penalty_1() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        dietary_sensitivity_data={
            "sugar": {
                "level": "low",
                "contains_sugar": True,
                "has_added_sugar": True,
                "sugar_sources": ["Sugar"],
            }
        }
    )
    payload = score_formulation(product)
    assert payload["penalties"]["B1_dietary_sugar"] == -1.0
    assert payload["metadata"]["dietary_sugar"]["reason"] == "low_added_sugar_source"


def test_b1_dietary_sugar_syrup_or_sugar_alcohol_penalty_2() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    syrup_product = _product(
        dietary_sensitivity_data={
            "sugar": {
                "level": "low",
                "contains_sugar": True,
                "sugar_sources": ["Glucose Syrup"],
            },
            "sweeteners": {
                "high_glycemic": ["Glucose Syrup"],
            },
        }
    )
    alcohol_product = _product(
        dietary_sensitivity_data={
            "sugar": {
                "level": "low",
                "contains_sugar": True,
                "sugar_sources": ["Maltitol Syrup"],
            },
            "sweeteners": {
                "sugar_alcohols": ["Maltitol Syrup"],
            },
        }
    )

    assert score_formulation(syrup_product)["penalties"]["B1_dietary_sugar"] == -2.0
    assert score_formulation(alcohol_product)["penalties"]["B1_dietary_sugar"] == -2.0


def test_b1_dietary_sugar_syrup_source_penalty_does_not_depend_on_sweetener_copy() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        dietary_sensitivity_data={
            "sugar": {
                "level": "low",
                "contains_sugar": True,
                "has_added_sugar": True,
                "sugar_sources": ["Corn Syrup"],
            },
            "sweeteners": {},
        }
    )

    payload = score_formulation(product)
    assert payload["penalties"]["B1_dietary_sugar"] == -2.0


def test_b1_dietary_sugar_clean_returns_zero() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(_product())
    assert payload["penalties"]["B1_dietary_sugar"] == 0.0


# --- P1.3.1b formulation-excellence components ---------------------------


def test_a5b_standardized_botanical_full_credit_for_percentage_evidence() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            formulation_data={
                "standardized_botanicals": [
                    {"name": "Ashwagandha", "meets_threshold": True, "evidence_source": "percentage_local"}
                ]
            }
        )
    )

    assert payload["components"]["A5b_standardized_botanical"] == 1.0


def test_a5b_standardized_botanical_marker_word_only_half_credit() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            formulation_data={
                "standardized_botanicals": [
                    {"name": "Milk Thistle", "meets_threshold": True, "evidence_source": "marker_word_only"}
                ]
            }
        )
    )

    assert payload["components"]["A5b_standardized_botanical"] == 0.5


def test_a5b_standardized_botanical_top_level_fallback() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(_product(has_standardized_botanical=True))

    assert payload["components"]["A5b_standardized_botanical"] == 1.0


def test_a5b_standardized_botanical_requires_threshold() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            formulation_data={
                "standardized_botanicals": [
                    {"name": "Ashwagandha", "meets_threshold": False, "evidence_source": "percentage_local"}
                ]
            }
        )
    )

    assert payload["components"]["A5b_standardized_botanical"] == 0.0


def test_a5c_synergy_cluster_tier_1_full_credit() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            formulation_data={
                "synergy_clusters": [
                    {
                        "evidence_tier": 1,
                        "match_count": 2,
                        "matched_ingredients": [
                            {"name": "Curcumin", "min_effective_dose": 500, "meets_minimum": True},
                            {"name": "Piperine", "min_effective_dose": 5, "meets_minimum": True},
                        ],
                    }
                ]
            }
        )
    )

    assert payload["components"]["A5c_synergy_cluster"] == 1.0


@pytest.mark.parametrize(
    ("tier", "expected"),
    [(2, 0.75), (3, 0.5), (4, 0.25), (99, 0.25)],
)
def test_a5c_synergy_cluster_tier_points(tier: int, expected: float) -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            formulation_data={
                "synergy_clusters": [
                    {
                        "evidence_tier": tier,
                        "match_count": 2,
                        "matched_ingredients": [
                            {"name": "A", "min_effective_dose": 100, "meets_minimum": True},
                            {"name": "B", "min_effective_dose": 100, "meets_minimum": False},
                        ],
                    }
                ]
            }
        )
    )

    assert payload["components"]["A5c_synergy_cluster"] == expected


def test_a5c_synergy_cluster_requires_two_matches_and_dose_checkable_items() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    single_match = score_formulation(
        _product(
            formulation_data={
                "synergy_clusters": [
                    {
                        "evidence_tier": 1,
                        "match_count": 1,
                        "matched_ingredients": [
                            {"name": "A", "min_effective_dose": 100, "meets_minimum": True},
                        ],
                    }
                ]
            }
        )
    )
    no_dose_checks = score_formulation(
        _product(
            formulation_data={
                "synergy_clusters": [
                    {
                        "evidence_tier": 1,
                        "match_count": 2,
                        "matched_ingredients": [{"name": "A"}, {"name": "B"}],
                    }
                ]
            }
        )
    )

    assert single_match["components"]["A5c_synergy_cluster"] == 0.0
    assert no_dose_checks["components"]["A5c_synergy_cluster"] == 0.0


def test_a5c_synergy_cluster_requires_half_of_checkable_items_dosed() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            formulation_data={
                "synergy_clusters": [
                    {
                        "evidence_tier": 1,
                        "match_count": 3,
                        "matched_ingredients": [
                            {"name": "A", "min_effective_dose": 100, "meets_minimum": True},
                            {"name": "B", "min_effective_dose": 100, "meets_minimum": False},
                            {"name": "C", "min_effective_dose": 100, "meets_minimum": False},
                        ],
                    }
                ]
            }
        )
    )

    assert payload["components"]["A5c_synergy_cluster"] == 0.0


def test_a5c_synergy_cluster_explicit_legacy_flag() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    true_payload = score_formulation(_product(synergy_cluster_qualified=True))
    false_payload = score_formulation(_product(synergy_cluster_qualified=False))

    assert true_payload["components"]["A5c_synergy_cluster"] == 0.75
    assert false_payload["components"]["A5c_synergy_cluster"] == 0.0


def test_a5d_non_gmo_project_verified_gets_half_point() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            labelText={
                "parsed": {
                    "certifications": ["Non-GMO-Project"],
                    "cleanLabelClaims": ["Non-GMO Project Verified"],
                }
            }
        )
    )

    assert payload["components"]["A5d_non_gmo"] == 0.5


def test_a5d_non_gmo_project_rules_db_evidence_gets_half_point() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            compliance_data={
                "evidence_based": {
                    "allergen_free_claims": [
                        {
                            "rule_id": "CLAIM_NON_GMO_PROJECT",
                            "dedupe_key": "dietary:non_gmo_project",
                            "display_name": "Non-GMO Project Verified",
                            "score_eligible": True,
                            "matched_text": "Non-GMO Project Verified",
                        }
                    ]
                }
            }
        )
    )

    assert payload["components"]["A5d_non_gmo"] == 0.5


def test_a5d_generic_non_gmo_claim_no_credit() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(labelText={"parsed": {"certifications": ["Non-GMO-General"], "cleanLabelClaims": ["Non-GMO"]}})
    )

    assert payload["components"]["A5d_non_gmo"] == 0.0


def test_a5_rollup_clamps_at_4_when_subcredits_exceed_cap() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        formulation_data={
            "organic": {"usda_verified": True},
            "standardized_botanicals": [
                {"name": "Ashwagandha", "meets_threshold": True, "evidence_source": "percentage_local"}
            ],
            "synergy_clusters": [
                {
                    "evidence_tier": 1,
                    "match_count": 2,
                    "matched_ingredients": [
                        {"name": "A", "min_effective_dose": 100, "meets_minimum": True},
                        {"name": "B", "min_effective_dose": 100, "meets_minimum": True},
                    ],
                }
            ],
        },
        labelText={"parsed": {"certifications": ["Non-GMO Project Verified"]}},
        ingredients=[_ingredient(natural=True)],
    )
    payload = score_formulation(product)

    assert payload["components"]["_A5_rollup_clamped_from"] == 4.5


# --- P1.3.1b enzyme recognition ------------------------------------------


def test_enzyme_recognition_named_single_ingredient_gets_half_point() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            supp_type="single_nutrient",
            ingredients=[
                _ingredient(name="Protease", canonical_id="protease", bio_score=10, quantity=100, unit="HUT")
            ],
        )
    )

    assert payload["components"]["enzyme_recognition"] == 0.5


def test_enzyme_recognition_dedupes_and_caps_at_two_points() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    rows = [
        _ingredient(name="Protease", canonical_id="protease", bio_score=10),
        _ingredient(name="Protease 4.5", canonical_id="protease_2", bio_score=10),
        _ingredient(name="Amylase", canonical_id="amylase", bio_score=10),
        _ingredient(name="Lipase", canonical_id="lipase", bio_score=10),
        _ingredient(name="Bromelain", canonical_id="bromelain", bio_score=10),
        _ingredient(name="Papain", canonical_id="papain", bio_score=10),
    ]
    payload = score_formulation(_product(supp_type="single_nutrient", ingredients=rows))

    assert payload["components"]["enzyme_recognition"] == 2.0


def test_enzyme_recognition_requires_named_enzyme() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            supp_type="single_nutrient",
            ingredients=[_ingredient(name="Digestive Enzyme Blend", canonical_id="enzyme_blend", bio_score=10)],
        )
    )

    assert payload["components"]["enzyme_recognition"] == 0.0


def test_enzyme_recognition_requires_single_ingredient_type() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            supp_type="multi",
            ingredients=[_ingredient(name="Protease", canonical_id="protease", bio_score=10)],
        )
    )

    assert payload["components"]["enzyme_recognition"] == 0.0


def test_blend_anchor_pancreatin_gets_iqm_formulation_credit() -> None:
    """Pancreatin-style enzyme products can have the dose on a blend/header
    row while no IQD scorable row exists. The scoring input contract derives a
    blend_anchor_mass row; generic formulation should use its conservative IQM
    form quality instead of reporting a false 0/30 formulation."""
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            ingredients=[],
            activeIngredients=[
                {
                    "name": "Pancreatin",
                    "standardName": "Digestive Enzymes",
                    "canonical_id": "digestive_enzymes",
                    "canonical_source_db": "ingredient_quality_map",
                    "quantity": 1.0,
                    "unit": "Gram(s)",
                    "source_section": "active",
                    "raw_source_path": "ingredientRows[0]",
                    "cleaner_row_role": "blend_header_total",
                    "score_eligible_by_cleaner": False,
                    "dose_class": "blend_total_weight",
                    "raw_taxonomy": {
                        "category": "blend",
                        "ingredientGroup": "Blend (non-nutrient/non-botanical)",
                        "forms": [{"name": "Porcine"}],
                    },
                }
            ],
        )
    )

    assert payload["components"]["A1_bio_score"] == 11.0
    assert payload["score"] > 0.0


# --- P1.3.1b safety/additive penalties -----------------------------------


def test_b0_high_risk_plus_watchlist_accumulate() -> None:
    # Multiple safety signals ACCUMULATE (was capped at -10). A high_risk (10) +
    # watchlist (5) now totals -15 so a product carrying more risk is tanked more.
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            contaminant_data={
                "banned_substances": {
                    "substances": [
                        {"name": "A", "status": "high_risk", "match_type": "exact"},
                        {"name": "B", "status": "watchlist", "match_type": "alias"},
                    ]
                }
            }
        )
    )

    assert payload["penalties"]["B0_moderate_watchlist"] == -15.0


def test_b0_two_high_risk_substances_penalize_as_two() -> None:
    # User directive: 2 high_risk must NOT score as 1. They accumulate to -20.
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            contaminant_data={
                "banned_substances": {
                    "substances": [
                        {"name": "A", "status": "high_risk", "match_type": "exact"},
                        {"name": "B", "status": "high_risk", "match_type": "exact"},
                    ]
                }
            }
        )
    )

    assert payload["penalties"]["B0_moderate_watchlist"] == -20.0


def test_b0_accumulation_bounded_by_dimension_cap() -> None:
    # Accumulation is bounded by the 30-pt formulation dimension (can fully eat it,
    # not exceed it). 4 high_risk would be -40 but clamps to -30.
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            contaminant_data={
                "banned_substances": {
                    "substances": [
                        {"name": f"H{i}", "status": "high_risk", "match_type": "exact"}
                        for i in range(4)
                    ]
                }
            }
        )
    )

    assert payload["penalties"]["B0_moderate_watchlist"] == -30.0


def test_b0_watchlist_exact_penalty_five() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            contaminant_data={
                "banned_substances": {
                    "substances": [{"name": "Watch", "status": "watchlist", "match_type": "exact"}]
                }
            }
        )
    )

    assert payload["penalties"]["B0_moderate_watchlist"] == -5.0


def test_b0_legacy_moderate_severity_with_exactish_match_penalty_ten() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            contaminant_data={
                "banned_substances": {
                    "substances": [
                        {
                            "name": "Legacy moderate",
                            "severity_level": "moderate",
                            "match_method": "exact_name",
                        }
                    ]
                }
            }
        )
    )

    assert payload["penalties"]["B0_moderate_watchlist"] == -10.0


def test_b0_non_exact_match_does_not_auto_penalize() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            contaminant_data={
                "banned_substances": {
                    "substances": [{"name": "Maybe", "status": "high_risk", "match_type": "fuzzy"}]
                }
            }
        )
    )

    assert payload["penalties"]["B0_moderate_watchlist"] == 0.0


def test_b1_harmful_additives_severity_points_and_sugar_stays_separate() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            contaminant_data={
                "harmful_additives": {
                    "additives": [
                        {"name": "A", "severity_level": "critical", "source_section": "inactive"},
                        {"name": "B", "severity_level": "high", "source_section": "inactive"},
                        {"name": "C", "severity_level": "moderate", "source_section": "inactive"},
                        {"name": "D", "severity_level": "low", "source_section": "inactive"},
                    ]
                }
            },
            dietary_sensitivity_data={"sugar": {"level": "high"}},
        )
    )

    assert payload["penalties"]["B1_harmful_additives"] == -6.5
    assert payload["penalties"]["B1_dietary_sugar"] == -4.0


def test_b1_harmful_additives_suppresses_low_and_moderate_actives_only() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(
        _product(
            contaminant_data={
                "harmful_additives": {
                    "additives": [
                        {"name": "Active low", "severity_level": "low", "source_section": "active"},
                        {"name": "Active moderate", "severity_level": "moderate", "source_section": "active"},
                        {"name": "Active high", "severity_level": "high", "source_section": "active"},
                        {"name": "Active critical", "severity_level": "critical", "source_section": "active"},
                    ]
                }
            }
        )
    )

    assert payload["penalties"]["B1_harmful_additives"] == -5.0


def test_b1_harmful_additives_dedupes_by_id_and_caps_at_15() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    rows = [
        {"additive_id": "dup", "severity_level": "low", "source_section": "inactive"},
        {"additive_id": "dup", "severity_level": "critical", "source_section": "inactive"},
    ]
    rows.extend(
        {"additive_id": f"x{i}", "severity_level": "critical", "source_section": "inactive"}
        for i in range(10)
    )
    payload = score_formulation(_product(contaminant_data={"harmful_additives": {"additives": rows}}))

    assert payload["penalties"]["B1_harmful_additives"] == -15.0


def test_b1_harmful_additives_anonymous_rows_do_not_dedupe_by_name() -> None:
    """v3 only dedupes rows with stable additive_id/id. Anonymous rows
    are treated as distinct, even when their display names match."""
    from scoring_v4.modules.generic_formulation import score_formulation

    rows = [
        {"name": "Same display name", "severity_level": "low", "source_section": "inactive"},
        {"name": "Same display name", "severity_level": "low", "source_section": "inactive"},
    ]
    payload = score_formulation(_product(contaminant_data={"harmful_additives": {"additives": rows}}))

    assert payload["penalties"]["B1_harmful_additives"] == -1.0


def test_p131b_metadata_marks_formulation_complete() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(_product())

    assert payload["phase"] == "P1.3.1b_formulation_complete"
    assert payload["metadata"]["phase"] == "P1.3.1b_formulation_complete"
    assert payload["metadata"]["deferred_components"] == []
    assert payload["metadata"]["deferred_penalties"] == []


# --- Dimension score assembly ---------------------------------------------


def test_dimension_score_assembles_8_components_minus_penalty() -> None:
    """Bisglycinate single 200mg, capsule, no other signals. Expected:
    bio_score 14 + premium 0 (skip-first) + delivery 2 (capsule = tier 2)
    + absorption 0 + A5a 0 + A5e 0 + A6 4 (v4.1 tiered, bio>=14 elite)
    - sugar 0 = 20.0, then premium-single floor lifts to 24.0."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        delivery_tier=2,
        ingredients=[_ingredient(bio_score=14, natural=False)],
    )
    payload = score_formulation(product)

    assert payload["score"] == 24.0
    assert payload["max"] == 30.0
    assert payload["components"]["premium_single_ingredient_floor_adjustment"] == 4.0


def test_dimension_score_clamps_to_max_30() -> None:
    """P1.3.1b brings enough positive components online that the 30-point
    dimension cap can be exercised directly."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        supp_type="single_nutrient",
        delivery_tier=1,
        absorption_enhancer_paired=True,
        formulation_data={"organic": {"usda_verified": True}},
        labelText={"parsed": {"certifications": ["Non-GMO Project Verified"]}},
        ingredients=[
            _ingredient(canonical_id="a", bio_score=15, natural=True),
            _ingredient(canonical_id="b", bio_score=15, natural=True),
            _ingredient(canonical_id="c", bio_score=15, natural=True),
            _ingredient(canonical_id="d", bio_score=15, natural=True),
            _ingredient(canonical_id="e", bio_score=15, natural=True),
            _ingredient(canonical_id="f", bio_score=15, natural=True),
            _ingredient(canonical_id="g", bio_score=15, natural=True),
            _ingredient(canonical_id="h", bio_score=15, natural=True),
            _ingredient(canonical_id="i", bio_score=15, natural=True),
            _ingredient(name="Amylase", canonical_id="amylase", bio_score=15, natural=True),
            _ingredient(name="Protease", canonical_id="protease", bio_score=15, natural=True),
            _ingredient(name="Lipase", canonical_id="lipase", bio_score=15, natural=True),
            _ingredient(name="Cellulase", canonical_id="cellulase", bio_score=15, natural=True),
        ],
    )
    product["formulation_data"]["standardized_botanicals"] = [
        {"name": "Ashwagandha", "meets_threshold": True, "evidence_source": "percentage_local"}
    ]
    product["formulation_data"]["synergy_clusters"] = [
        {
            "evidence_tier": 1,
            "match_count": 2,
            "matched_ingredients": [
                {"name": "A", "min_effective_dose": 100, "meets_minimum": True},
                {"name": "B", "min_effective_dose": 100, "meets_minimum": True},
            ],
        }
    ]
    payload = score_formulation(product)

    assert payload["score"] <= 30.0, "dimension cap must hold"
    assert payload["score"] == 30.0


def test_dimension_score_floors_at_zero() -> None:
    """A clean unmapped product with sugar penalty alone shouldn't go
    negative — score floors at 0."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        ingredients=[_ingredient(bio_score=0)],
        dietary_sensitivity_data={"sugar": {"level": "high"}},
    )
    payload = score_formulation(product)
    assert payload["score"] >= 0.0


def test_dimension_score_handles_empty_product() -> None:
    """Malformed input must not raise; returns score 0 and a fully-shaped
    breakdown so audit tooling can carry on."""
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(None)  # type: ignore[arg-type]
    assert payload["score"] == 0.0
    assert payload["max"] == 30.0
    assert "A1_bio_score" in payload["components"]
    assert "B1_dietary_sugar" in payload["penalties"]


# --- Worked example: Thorne Magnesium Bisglycinate (canary row 1) --------


def test_thorne_mg_bisglycinate_formulation_band() -> None:
    """Worked example from §6 line 424. Expected:
      A1 bio_score ~14 (bisglycinate, single ingredient)
      A2 premium_forms 0 (one premium form, skip-first)
      A3 delivery 2 (capsule, tier 2)
      A4 absorption 0 (no enhancer pairing)
      A5a organic 0 (not USDA-verified)
      A5e natural 0 (synthetic chelate)
      A6 single-ingredient 4 (v4.1 tiered: single + bio≥14 elite tier)
      - sugar 0
      = ~20 before the premium-single floor. The top-band ceiling fix lifts
      elite focused singles to 24 without changing weak singles or multis."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        supp_type="single_nutrient",
        delivery_tier=2,
        ingredients=[
            _ingredient(
                name="Magnesium Bisglycinate",
                canonical_id="magnesium_bisglycinate",
                bio_score=14,
                quantity=200,
                unit="mg",
                natural=False,
            )
        ],
    )
    payload = score_formulation(product)

    assert payload["score"] == 24.0
    assert payload["metadata"]["premium_single_ingredient_floor"]["applied"] is True


# --- Shadow integration ---------------------------------------------------


def test_shadow_populates_formulation_when_generic() -> None:
    from score_supplements_v4 import score_product_v4

    product = _product(
        supp_type="single_nutrient",
        delivery_tier=2,
        ingredients=[_ingredient(bio_score=14)],
    )
    out = score_product_v4(product)

    module_block = out["v4_breakdown"]["module"]
    assert module_block["module"] == "generic"
    formulation = module_block["dimensions"]["formulation"]
    assert formulation["score"] is not None
    assert formulation["score"] > 0
    assert formulation["max"] == 30.0
    assert "A1_bio_score" in formulation["components"]
    assert "B1_dietary_sugar" in formulation["penalties"]
    assert formulation["metadata"]["phase"] == "P1.3.1b_formulation_complete"
    assert formulation["metadata"]["deferred_components"] == []
    assert formulation["metadata"]["deferred_penalties"] == []
    # Module-level phase now reflects the Phase 9 rubric-is-score assembly;
    # formulation's own metadata still records the P1.3.1b sub-slice.
    assert module_block["phase"] == "P9_rubric_is_score"


def test_shadow_top_level_score_populated_at_p136() -> None:
    """P1.3.6 final assembly populates top-level raw_score_v4_100."""
    from score_supplements_v4 import score_product_v4

    out = score_product_v4(
        _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=14)])
    )
    assert out["raw_score_v4_100"] is not None
    assert out["v4_confidence"] in {"high", "moderate", "low"}
    assert out["v4_breakdown"]["confidence"]["band"] == out["v4_confidence"]


def test_shadow_transparency_populated_at_p135() -> None:
    """Originally asserted dose/evidence/trust/transparency all stay
    skeleton after formulation lands. After P1.3.2a, dose is online via
    the RDA/UL proxy. After P1.3.3, evidence is also online. After
    P1.3.4, Trust is online; after P1.3.5 transparency is online."""
    from score_supplements_v4 import score_product_v4

    out = score_product_v4(
        _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=14)])
    )
    module_block = out["v4_breakdown"]["module"]
    for name in ("transparency",):
        dim = module_block["dimensions"][name]
        assert dim["score"] == 9.0
        assert dim["components"]["clear_disclosure_base"] == 6.0
        assert dim["components"]["complete_active_identity_dose_disclosure"] == 3.0
        assert dim["metadata"]["phase"] == "P1.3.5_transparency"

    evidence = module_block["dimensions"]["evidence"]
    assert evidence["score"] == 0.0
    assert "clinical_evidence_pipeline" in evidence["components"]

    # Phase 4: trust is now the additive verification_bonus (0-8).
    verification = module_block["verification_bonus"]
    assert verification["metadata"]["source_trust_score_0_15"] == 0.0
    assert "B4a_verified_certifications" in verification["components"]


# --- Architecture lock ----------------------------------------------------


def test_generic_formulation_does_not_import_v3_scorer() -> None:
    import scoring_v4.modules.generic_formulation as gf

    source = Path(gf.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source


def test_generic_helpers_does_not_import_v3_scorer() -> None:
    import scoring_v4.modules.generic_helpers as gh

    source = Path(gh.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source
