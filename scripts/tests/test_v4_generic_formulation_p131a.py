"""v4 Generic Formulation dimension — P1.3.1a tests.

Covers the 8 simple sub-rubrics implemented in this slice:
  A1 bio_score, A2 premium forms, A3 delivery, A4 absorption,
  A5a organic, A5e natural source, A6 single-ingredient,
  B1 dietary sugar penalty.

The 6 complex sub-rubrics (A5b std botanical, A5c synergy 4-tier,
A5d non-GMO, enzyme recognition, B0 moderate/watchlist, B1 harmful
additives) are stubbed at 0.0 and exercised in P1.3.1b tests.

Tests target the module API (`score_formulation`) directly AND verify
the shadow scorer wires the partial dimension score through.
"""

from __future__ import annotations

import sys
from pathlib import Path

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
    assert payload["components"]["A2_premium_forms"] == 0.0


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
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=14)])
    payload = score_formulation(product)
    assert payload["components"]["A6_single_ingredient"] == 1.0


def test_a6_single_ingredient_skipped_for_non_single_supp_type() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="multivitamin", ingredients=[_ingredient(bio_score=14)])
    payload = score_formulation(product)
    assert payload["components"]["A6_single_ingredient"] == 0.0


def test_a6_single_ingredient_low_bio_returns_zero() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=10)])
    payload = score_formulation(product)
    assert payload["components"]["A6_single_ingredient"] == 0.0


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


# --- B1 dietary sugar penalty ---------------------------------------------


def test_b1_dietary_sugar_high_penalty_1_5() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(dietary_sensitivity_data={"sugar": {"level": "high"}})
    payload = score_formulation(product)
    assert payload["penalties"]["B1_dietary_sugar"] == -1.5


def test_b1_dietary_sugar_moderate_penalty_0_5() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(dietary_sensitivity_data={"sugar": {"level": "moderate"}})
    payload = score_formulation(product)
    assert payload["penalties"]["B1_dietary_sugar"] == -0.5


def test_b1_dietary_sugar_clean_returns_zero() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(_product())
    assert payload["penalties"]["B1_dietary_sugar"] == 0.0


# --- Stubs / deferred -----------------------------------------------------


def test_p131b_components_stubbed_to_zero() -> None:
    """The 4 complex components deferred to P1.3.1b are recorded as 0.0
    so the breakdown shape stays stable and audit tooling can distinguish
    'deferred' from 'absent in blob'."""
    from scoring_v4.modules.generic_formulation import (
        DEFERRED_TO_P131B_COMPONENTS,
        score_formulation,
    )

    payload = score_formulation(_product())
    for name in DEFERRED_TO_P131B_COMPONENTS:
        assert payload["components"][name] == 0.0


def test_p131b_penalties_stubbed_to_zero() -> None:
    from scoring_v4.modules.generic_formulation import (
        DEFERRED_TO_P131B_PENALTIES,
        score_formulation,
    )

    payload = score_formulation(_product())
    for name in DEFERRED_TO_P131B_PENALTIES:
        assert payload["penalties"][name] == 0.0


def test_phase_marker_partial() -> None:
    from scoring_v4.modules.generic_formulation import score_formulation

    payload = score_formulation(_product())
    assert payload["phase"] == "P1.3.1a_partial"


def test_deferred_metadata_lists_p131b_components_and_penalties() -> None:
    """Audit tooling should not infer deferred state from zero-valued
    stubs. The payload emits explicit metadata."""
    from scoring_v4.modules.generic_formulation import (
        DEFERRED_TO_P131B_COMPONENTS,
        DEFERRED_TO_P131B_PENALTIES,
        score_formulation,
    )

    payload = score_formulation(_product())

    assert payload["metadata"]["phase"] == "P1.3.1a_partial"
    assert payload["metadata"]["deferred_components"] == list(DEFERRED_TO_P131B_COMPONENTS)
    assert payload["metadata"]["deferred_penalties"] == list(DEFERRED_TO_P131B_PENALTIES)


# --- Dimension score assembly ---------------------------------------------


def test_dimension_score_assembles_8_components_minus_penalty() -> None:
    """Bisglycinate single 200mg, capsule, no other signals. Expected:
    bio_score 14 + premium 0 (skip-first) + delivery 2 (capsule = tier 2)
    + absorption 0 + A5a 0 + A5e 0 + A6 1 - sugar 0 = 17.0."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        delivery_tier=2,
        ingredients=[_ingredient(bio_score=14, natural=False)],
    )
    payload = score_formulation(product)

    assert payload["score"] == 17.0
    assert payload["max"] == 30.0


def test_dimension_score_clamps_to_max_30() -> None:
    """At P1.3.1a, maximum positive sum is 15+4+3+3+2+1 = 28 (the A5
    rollup is capped at 4 but only A5a+A5e are online = max 2). The
    30-clamp can't actually be exercised from positives alone until
    P1.3.1b lands A5b/A5c/A5d/enzyme. This test asserts the clamp is
    in effect (score ≤ 30) and locks the P1.3.1a observed ceiling at 28."""
    from scoring_v4.modules.generic_formulation import score_formulation

    product = _product(
        supp_type="single_nutrient",
        delivery_tier=1,
        absorption_enhancer_paired=True,
        formulation_data={"organic": {"usda_verified": True}},
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
        ],
    )
    payload = score_formulation(product)

    assert payload["score"] <= 30.0, "dimension cap must hold"
    assert payload["score"] == 28.0, "P1.3.1a observed max from 8 components"


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


def test_thorne_mg_bisglycinate_partial_formulation_band() -> None:
    """Worked example from §6 line 424. v4 P1.3.1a expected (8 components):
      A1 bio_score ~14 (bisglycinate, single ingredient)
      A2 premium_forms 0 (one premium form, skip-first)
      A3 delivery 2 (capsule, tier 2)
      A4 absorption 0 (no enhancer pairing)
      A5a organic 0 (not USDA-verified)
      A5e natural 0 (synthetic chelate)
      A6 single-ingredient 1 (single + bio≥14)
      - sugar 0
      = ~17 partial. Final number lands after P1.3.1b adds standardized/
      synergy/non-GMO/enzyme/B0/B1_additives."""
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

    # Expected partial band: 16-19 (matches §6 ~18.5 v3 baseline minus
    # the not-yet-implemented A5b/A5c/A5d/enzyme credits).
    assert 16.0 <= payload["score"] <= 19.0


# --- Shadow integration ---------------------------------------------------


def test_shadow_populates_formulation_partial_when_generic() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _product(
        supp_type="single_nutrient",
        delivery_tier=2,
        ingredients=[_ingredient(bio_score=14)],
    )
    out = score_product_v4_shadow(product)

    module_block = out["shadow_score_v4_breakdown"]["module"]
    assert module_block["module"] == "generic"
    formulation = module_block["dimensions"]["formulation"]
    assert formulation["score"] is not None
    assert formulation["score"] > 0
    assert formulation["max"] == 30.0
    assert "A1_bio_score" in formulation["components"]
    assert "B1_dietary_sugar" in formulation["penalties"]
    assert formulation["metadata"]["phase"] == "P1.3.1a_partial"
    assert "A5b_standardized_botanical" in formulation["metadata"]["deferred_components"]
    # Module phase reflects P1.3.1a.
    assert module_block["phase"] == "P1.3.1a_formulation_partial"


def test_shadow_top_level_score_still_none_at_p131a() -> None:
    """score_100 only populates at P1.3.6 final assembly. Top-level
    shadow_score_v4_100 stays None throughout P1.3.x."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(
        _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=14)])
    )
    assert out["shadow_score_v4_100"] is None
    assert out["shadow_score_v4_confidence"] == "skeleton"


def test_shadow_other_dimensions_still_skeleton_at_p131a() -> None:
    """Only formulation is online. dose/evidence/trust/transparency stay
    score=None with empty components/penalties until P1.3.2-P1.3.5."""
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(
        _product(supp_type="single_nutrient", ingredients=[_ingredient(bio_score=14)])
    )
    module_block = out["shadow_score_v4_breakdown"]["module"]
    for name in ("dose", "evidence", "trust", "transparency"):
        dim = module_block["dimensions"][name]
        assert dim["score"] is None, f"{name}.score should still be None at P1.3.1a"
        assert dim["components"] == {}
        assert dim["penalties"] == {}


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
