"""v4 Generic Evidence dimension — P1.3.3 tests.

The generic Evidence dimension preserves the Section C multiplicative
pipeline:

    study_type × evidence_level × effect_direction × enrollment × dose_guard
    → cap per ingredient → top-N weights → depth bonus → cap 20

The tests use the public `score_evidence()` entry point and the shadow
module wiring. They intentionally avoid v3 imports.
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
    name: str = "Magnesium",
    standard_name: str | None = None,
    canonical_id: str = "magnesium",
    quantity: float = 200,
    unit: str = "mg",
) -> dict:
    return {
        "name": name,
        "standard_name": standard_name or name,
        "canonical_id": canonical_id,
        "mapped": True,
        "quantity": quantity,
        "unit": unit,
    }


def _match(
    *,
    id: str = "INGR_MAGNESIUM_GENERIC",
    ingredient: str = "Magnesium",
    standard_name: str = "Magnesium",
    study_type: str = "systematic_review_meta",
    evidence_level: str = "ingredient-human",
    effect_direction: str = "positive_strong",
    total_enrollment: float | None = 8563,
    published_studies_count: float | None = None,
    **extra,
) -> dict:
    row = {
        "id": id,
        "ingredient": ingredient,
        "standard_name": standard_name,
        "study_type": study_type,
        "evidence_level": evidence_level,
        "effect_direction": effect_direction,
    }
    if total_enrollment is not None:
        row["total_enrollment"] = total_enrollment
    if published_studies_count is not None:
        row["published_studies_count"] = published_studies_count
    row.update(extra)
    return row


def _product(*, ingredients: list | None = None, matches: list | None = None) -> dict:
    rows = ingredients if ingredients is not None else [_ingredient()]
    return {
        "status": "active",
        "form_factor": "capsule",
        "supplement_type": {"type": "single_nutrient"},
        "ingredient_quality_data": {
            "ingredients_scorable": rows,
            "ingredients": rows,
        },
        "evidence_data": {
            "clinical_matches": matches if matches is not None else [_match()],
        },
    }


def test_evidence_payload_shape_and_phase() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(_product())

    assert payload["max"] == 20.0
    assert payload["phase"] == "P1.3.3_evidence_pipeline"
    assert "clinical_evidence_pipeline" in payload["components"]
    assert "depth_bonus" in payload["components"]
    assert payload["penalties"] == {}
    assert payload["metadata"]["phase"] == "P1.3.3_evidence_pipeline"


def test_magnesium_style_meta_analysis_scores_6_48() -> None:
    """6 base × 0.9 ingredient-human × 1.0 positive × 1.2 enrollment
    = 6.48 before depth. Strong ingredient-human meta-analyses should
    clear the low-evidence diagnostic threshold without claiming product-
    specific RCT certainty."""
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(_product())

    assert payload["score"] == 6.48
    assert payload["components"]["clinical_evidence_pipeline"] == 6.48
    assert payload["metadata"]["ingredient_points"]["magnesium"] == 6.48


def test_ksm66_branded_rct_scores_4_5_not_zero() -> None:
    """KSM-66 canary: branded-RCT evidence is recognized and not collapsed
    to generic Withania. Calibration can change later; matching must work."""
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(
        _product(
            ingredients=[
                _ingredient(
                    name="KSM-66 Ashwagandha",
                    standard_name="Ashwagandha",
                    canonical_id="ashwagandha",
                    quantity=600,
                    unit="mg",
                )
            ],
            matches=[
                _match(
                    id="BRAND_KSM66",
                    ingredient="KSM-66",
                    standard_name="KSM-66",
                    study_type="rct_multiple",
                    evidence_level="branded-rct",
                    total_enrollment=200,
                )
            ],
        )
    )

    assert payload["score"] == 4.5
    assert payload["metadata"]["ingredient_points"]["ksm 66"] == 4.5


def test_effect_direction_null_downweights_but_does_not_drop_to_zero() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(
        _product(matches=[_match(effect_direction="null", total_enrollment=8563)])
    )

    assert payload["score"] == 1.62


def test_effect_direction_negative_scores_zero() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(_product(matches=[_match(effect_direction="negative")]))

    assert payload["score"] == 0.0


def test_enrollment_multiplier_only_for_rct_and_meta() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    rct = score_evidence(
        _product(matches=[_match(study_type="rct_single", evidence_level="product-human", total_enrollment=30)])
    )
    observational = score_evidence(
        _product(matches=[_match(study_type="observational", evidence_level="product-human", total_enrollment=30)])
    )

    assert rct["score"] == 2.4  # 4 × 1 × 0.6
    assert observational["score"] == 2.0  # no enrollment penalty


def test_subclinical_dose_guard_applies_when_product_dose_below_minimum() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(
        _product(
            ingredients=[_ingredient(quantity=100, unit="mg")],
            matches=[_match(min_clinical_dose=200, dose_unit="mg")],
        )
    )

    assert payload["score"] == 1.62
    assert payload["metadata"]["flags"] == ["SUB_CLINICAL_DOSE_DETECTED"]
    assert payload["metadata"]["sub_clinical_canonicals"] == ["magnesium"]


def test_supra_clinical_dose_records_flag_without_penalty() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(
        _product(
            ingredients=[_ingredient(quantity=1200, unit="mg")],
            matches=[_match(min_clinical_dose=100, max_clinical_dose=300, dose_unit="mg")],
        )
    )

    assert payload["score"] == 6.48
    assert payload["metadata"]["flags"] == ["SUPRA_CLINICAL_DOSE"]


def test_marker_confidence_scale_reduces_secondary_marker_credit() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(_product(matches=[_match(marker_confidence_scale=0.5)]))

    assert payload["score"] == 3.24


def test_duplicate_entries_are_counted_once() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    m = _match(id="DUP")
    payload = score_evidence(_product(matches=[m, dict(m)]))

    assert payload["score"] == 6.48
    assert payload["metadata"]["matched_entries"] == 1


def test_top_n_weights_apply_after_per_ingredient_cap() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(
        _product(
            matches=[
                _match(id="A", ingredient="A", standard_name="A", evidence_level="product-human"),
                _match(id="B", ingredient="B", standard_name="B", evidence_level="product-human"),
                _match(id="C", ingredient="C", standard_name="C", evidence_level="product-human"),
                _match(id="D", ingredient="D", standard_name="D", evidence_level="product-human"),
                _match(id="E", ingredient="E", standard_name="E", evidence_level="product-human"),
            ]
        )
    )

    # Each ingredient caps at 7; top-N weights [1.0, 0.7, 0.5, 0.3],
    # fifth ignored. 7 * 2.5 = 17.5.
    assert payload["score"] == 17.5
    assert payload["metadata"]["top_n_applied"] == 4


def test_depth_bonus_uses_published_studies_count_bands() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(_product(matches=[_match(published_studies_count=40)]))

    assert payload["components"]["depth_bonus"] == 0.5
    assert payload["score"] == 6.98


def test_depth_bonus_uses_registry_completed_trials_when_count_absent() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(_product(matches=[_match(registry_completed_trials_count=40)]))

    assert payload["components"]["depth_bonus"] == 0.5


def test_collagen_primary_recovers_verified_evidence_when_enrichment_dropped_match() -> None:
    """Garden-of-Life collagen canary: the enriched product can carry a
    canonical collagen active/product-level evidence row while
    evidence_data.clinical_matches is empty. v4 should recover the verified
    collagen-peptides evidence instead of assigning Evidence=0.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    product = _product(
        ingredients=[
            _ingredient(
                name="Collagen Peptides",
                standard_name="Collagen",
                canonical_id="collagen",
                quantity=20,
                unit="Gram(s)",
            ),
            _ingredient(
                name="Bacillus coagulans SNZ-1969",
                standard_name="Bacillus Coagulans",
                canonical_id="bacillus_coagulans",
                quantity=2.5,
                unit="mg",
            ),
        ],
        matches=[],
    )

    payload = score_evidence(product, apply_primary_floor=True)

    # 3-lane model (2026-06-06): recovered collagen evidence is generic
    # (ingredient-human, not brand-specific), so it floors to the non-branded
    # strong tier (14), not 18. Collagen products get their real score from the
    # collagen_profile module; this is a dropped-evidence fallback. (Collagen is
    # a candidate for the consensus allowlist — broad generic evidence, 26 studies
    # — but is left off pending review since peptide MW/profile is form-sensitive.)
    assert payload["score"] == 14.0
    assert payload["components"]["primary_evidence_floor"] == 14.0
    assert payload["metadata"]["primary_evidence_floor_canonical"] == "collagen"
    assert payload["metadata"]["recovered_matches"] == ["RECOVERED_COLLAGEN_PEPTIDES_V1"]


def test_token_collagen_addon_does_not_recover_primary_collagen_evidence() -> None:
    """A multi/nutrient product with trace collagen is not a collagen product;
    recovery must not float it on collagen evidence.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    product = _product(
        ingredients=[
            _ingredient(
                name="Vitamin C",
                standard_name="Vitamin C",
                canonical_id="vitamin_c",
                quantity=500,
                unit="mg",
            ),
            _ingredient(
                name="Collagen Peptides",
                standard_name="Collagen",
                canonical_id="collagen",
                quantity=100,
                unit="mg",
            ),
        ],
        matches=[],
    )

    payload = score_evidence(product, apply_primary_floor=True)

    # Collagen (trace) must NOT recover/float the product on collagen evidence.
    assert payload["metadata"]["recovered_matches"] == []
    # P5 (2026-06): Vitamin C is the mass-dominant essential DRI nutrient, so it
    # earns the nutrition-authority floor (10) on its OWN necessity — never via the
    # trace collagen. The collagen-recovery guard is unaffected.
    assert payload["metadata"]["nutrition_authority_canonical"] == "vitamin_c"
    assert payload["score"] == 10.0


def test_gelatin_does_not_recover_hydrolyzed_collagen_peptides_evidence() -> None:
    """Gelatin is a separate collagen subtype; do not borrow the hydrolyzed
    collagen-peptides evidence fallback.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    product = _product(
        ingredients=[
            _ingredient(
                name="Gelatin",
                standard_name="Collagen",
                canonical_id="collagen",
                quantity=1.3,
                unit="Gram(s)",
            )
        ],
        matches=[],
    )
    product["ingredient_quality_data"]["ingredients_scorable"][0]["matched_form"] = "gelatin"
    product["ingredient_quality_data"]["ingredients_scorable"][0]["collagen_subtype"] = "gelatin"

    payload = score_evidence(product, apply_primary_floor=True)

    assert payload["score"] == 0.0
    assert payload["metadata"]["recovered_matches"] == []


def test_blend_anchor_brand_row_recovers_verified_product_level_evidence() -> None:
    """Relora-style products can have a dose-bearing branded blend anchor while
    enrichment missed the matching clinical-evidence row. Recovery must use the
    exact verified brand identity from backed_clinical_studies, not fuzzy text.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    product = _product(ingredients=[], matches=[])
    product["product_name"] = "Relora"
    product["product_scoring_evidence"] = [
        {
            "name": "Relora Patented Proprietary Blend",
            "canonical_id": "relora_patented_proprietary_blend",
            "clean_identity_id": "relora_patented_proprietary_blend",
            "scoring_parent_id": "relora_patented_proprietary_blend",
            "evidence_canonical_id": "relora_patented_proprietary_blend",
            "canonical_source_db": "product_scoring_evidence",
            "evidence_origin": "compatibility_derived",
            "evidence_type": "blend_anchor_mass",
            "scoreable": True,
            "scoreable_identity": True,
            "score_eligible_by_cleaner": True,
            "dose_class": "therapeutic_mass",
            "dose_value": 250,
            "dose_unit": "mg",
            "source": "activeIngredients",
            "raw_source_path": "ingredientRows[0]",
            "evidence_scope": "blend_level",
            "linked_rows": ["ingredientRows[0]"],
            "confidence": "medium",
            "reason": "identity_bearing_blend_header_mass",
        }
    ]

    payload = score_evidence(product, apply_primary_floor=True)

    assert payload["metadata"]["recovered_matches"] == ["BRAND_RELORA"]
    assert payload["metadata"]["matched_entries"] == 1
    assert payload["components"]["primary_evidence_floor"] == 17.0
    assert payload["metadata"]["primary_evidence_floor_canonical"] == "relora"
    assert payload["score"] == 17.0


def test_branded_recovery_does_not_borrow_relora_for_generic_magnolia_blend() -> None:
    """Relora's product-specific RCT must not float a generic
    magnolia-phellodendron blend that does not say Relora on the label.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    product = _product(ingredients=[], matches=[])
    product["product_name"] = "Magnolia Phellodendron Extract"
    product["product_scoring_evidence"] = [
        {
            "name": "Magnolia Phellodendron Extract Proprietary Blend",
            "canonical_id": "magnolia_phellodendron_extract",
            "clean_identity_id": "magnolia_phellodendron_extract",
            "scoring_parent_id": "magnolia_phellodendron_extract",
            "evidence_canonical_id": "magnolia_phellodendron_extract",
            "canonical_source_db": "product_scoring_evidence",
            "evidence_origin": "compatibility_derived",
            "evidence_type": "blend_anchor_mass",
            "scoreable": True,
            "scoreable_identity": True,
            "score_eligible_by_cleaner": True,
            "dose_class": "therapeutic_mass",
            "dose_value": 250,
            "dose_unit": "mg",
            "source": "activeIngredients",
            "raw_source_path": "ingredientRows[0]",
            "evidence_scope": "blend_level",
            "linked_rows": ["ingredientRows[0]"],
            "confidence": "medium",
            "reason": "identity_bearing_blend_header_mass",
        }
    ]

    payload = score_evidence(product, apply_primary_floor=True)

    assert payload["score"] == 0.0
    assert payload["metadata"]["recovered_matches"] == []


def test_exact_single_active_recovers_verified_ingredient_human_evidence() -> None:
    """Exact, dose-bearing single actives should recover their verified
    ingredient-human backed entries when enrichment omitted the match.

    This must stay exact and primary-active gated; generic ingredient recovery
    is not fuzzy text matching and must not borrow evidence for trace add-ons.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    product = _product(
        ingredients=[
            _ingredient(
                name="NAC 600 mg",
                standard_name="N-Acetylcysteine",
                canonical_id="nac",
                quantity=600,
                unit="mg",
            )
        ],
        matches=[],
    )

    payload = score_evidence(product, apply_primary_floor=True)

    assert payload["metadata"]["recovered_matches"] == ["INGR_NAC"]
    assert payload["metadata"]["matched_entries"] == 1
    assert payload["components"]["clinical_evidence_pipeline"] == 3.888
    assert payload["components"]["primary_evidence_floor"] == 8.4
    assert payload["metadata"]["primary_evidence_floor_canonical"] == "n acetylcysteine"
    assert payload["score"] == 8.4


def test_non_nac_primary_active_recovers_verified_ingredient_human_evidence() -> None:
    """The recovery is a contract fix, not an NAC patch."""
    from scoring_v4.modules.generic_evidence import score_evidence

    product = _product(
        ingredients=[
            _ingredient(
                name="Ashwagandha Root 600 mg",
                standard_name="Ashwagandha",
                canonical_id="ashwagandha",
                quantity=600,
                unit="mg",
            )
        ],
        matches=[],
    )

    payload = score_evidence(product, apply_primary_floor=True)

    assert payload["metadata"]["recovered_matches"] == ["INGR_ASHWAGANDHA"]
    assert payload["components"]["primary_evidence_floor"] == 14.0
    assert payload["score"] == 14.0


def test_l_glycine_alias_recovers_existing_glycine_evidence() -> None:
    """L-glycine products should match the existing verified glycine entry.

    This is a deterministic identity bridge: it does not add a new study or
    borrow evidence from an unrelated ingredient.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    product = _product(
        ingredients=[
            _ingredient(
                name="L-Glycine",
                standard_name="L-Glycine",
                canonical_id="l_glycine",
                quantity=3000,
                unit="mg",
            )
        ],
        matches=[],
    )

    payload = score_evidence(product, apply_primary_floor=True)

    assert payload["metadata"]["recovered_matches"] == ["INGR_GLYCINE"]
    assert payload["metadata"]["matched_entries"] == 1
    assert payload["score"] > 0.0


def test_trace_active_does_not_recover_generic_ingredient_evidence() -> None:
    """A trace NAC add-on should not float an unrelated mass-primary product on
    NAC's generic ingredient evidence.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    product = _product(
        ingredients=[
            _ingredient(
                name="Vitamin C",
                standard_name="Vitamin C",
                canonical_id="vitamin_c",
                quantity=500,
                unit="mg",
            ),
            _ingredient(
                name="NAC",
                standard_name="N-Acetylcysteine",
                canonical_id="nac",
                quantity=5,
                unit="mg",
            ),
        ],
        matches=[],
    )

    payload = score_evidence(product, apply_primary_floor=True)

    assert payload["metadata"]["recovered_matches"] == []
    assert payload["metadata"]["nutrition_authority_canonical"] == "vitamin_c"
    assert payload["score"] == 10.0


def test_folate_mcg_dfe_gets_nutrition_authority_floor() -> None:
    """Qualified folate units are still mass units for the DRI-essential floor.

    Regression for labels like "Methyl Folate 1,000 mcg DFE": the scorer used
    to treat `mcg DFE` as non-mass and missed the vitamin_b9_folate authority
    floor, producing evidence=0 despite a dose-bearing essential nutrient row.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    product = _product(
        ingredients=[
            _ingredient(
                name="Magnafolate C",
                standard_name="Vitamin B9 (Folate)",
                canonical_id="vitamin_b9_folate",
                quantity=1000,
                unit="mcg DFE",
            )
        ],
        matches=[],
    )

    payload = score_evidence(product, apply_primary_floor=True)

    assert payload["metadata"]["nutrition_authority_canonical"] == "vitamin_b9_folate"
    assert payload["score"] == 10.0


def test_hidden_coactive_does_not_recover_generic_ingredient_evidence() -> None:
    """A mass-dominant co-active still needs to be clear from the product title
    unless it is the only scorable active.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    product = _product(
        ingredients=[
            _ingredient(
                name="Lithium Orotate",
                standard_name="Lithium",
                canonical_id="lithium",
                quantity=5,
                unit="mg",
            ),
            _ingredient(
                name="NAC",
                standard_name="N-Acetylcysteine",
                canonical_id="nac",
                quantity=200,
                unit="mg",
            ),
        ],
        matches=[],
    )
    product["product_name"] = "Lithium Orotate 5 mg"
    product["fullName"] = "Lithium Orotate 5 mg"

    payload = score_evidence(product, apply_primary_floor=True)

    assert payload["metadata"]["recovered_matches"] == []
    assert payload["score"] == 0.0


def test_no_matches_scores_zero_not_none() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(_product(matches=[]))

    assert payload["score"] == 0.0
    assert payload["metadata"]["matched_entries"] == 0


def test_reference_only_evidence_level_scores_zero() -> None:
    """Authority pages and fact sheets are context, not clinical evidence.

    They may live in backed_clinical_studies for display/provenance, but
    `evidence_level=reference` must not produce Evidence points.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence(
        _product(matches=[_match(study_type="reference", evidence_level="reference")])
    )

    assert payload["score"] == 0.0
    assert payload["components"]["clinical_evidence_pipeline"] == 0.0
    assert payload["metadata"]["matched_entries"] == 1


def test_shadow_wires_evidence_dimension() -> None:
    from score_supplements_v4 import score_product_v4

    out = score_product_v4(_product())

    evidence = out["v4_breakdown"]["module"]["dimensions"]["evidence"]
    # Phase 8: the generic module opts into the primary-ingredient floor. The
    # default product's mass-primary magnesium has a systematic_review_meta
    # positive match -> floored to 14.0 (non-branded strong; 3-lane model 2026-06-06:
    # magnesium is form-dependent, not a consensus gold-standard generic).
    assert evidence["score"] == 14.0
    assert evidence["metadata"]["primary_evidence_floor"] == 14.0
    assert evidence["max"] == 20.0
    assert evidence["metadata"]["phase"] == "P1.3.3_evidence_pipeline"


def test_primary_floor_mirrors_mixed_effect_multiplier() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    # P5: use a NON-essential primary (ashwagandha) so the clinical effect-multiplier
    # is tested in isolation from the DRI nutrition-authority floor (essentials -> 10).
    payload = score_evidence(
        _product(
            ingredients=[_ingredient(name="Ashwagandha", canonical_id="ashwagandha", quantity=600)],
            matches=[_match(id="INGR_ASHWAGANDHA", ingredient="Ashwagandha",
                            standard_name="Ashwagandha", effect_direction="mixed")],
        ),
        apply_primary_floor=True,
    )

    assert payload["score"] == 8.4
    assert payload["components"]["primary_evidence_floor"] == 8.4
    assert payload["metadata"]["primary_evidence_floor"] == 8.4
    assert payload["metadata"]["primary_evidence_floor_canonical"] == "ashwagandha"


def test_primary_floor_mirrors_null_effect_multiplier() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    # P5: non-essential primary (ashwagandha) isolates the null-effect multiplier
    # from the DRI nutrition-authority floor.
    payload = score_evidence(
        _product(
            ingredients=[_ingredient(name="Ashwagandha", canonical_id="ashwagandha", quantity=600)],
            matches=[_match(id="INGR_ASHWAGANDHA", ingredient="Ashwagandha",
                            standard_name="Ashwagandha", effect_direction="null")],
        ),
        apply_primary_floor=True,
    )

    assert payload["score"] == 3.5
    assert payload["components"]["primary_evidence_floor"] == 3.5
    assert payload["metadata"]["primary_evidence_floor"] == 3.5


def test_primary_floor_still_rejects_negative_effect() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    # P5: non-essential primary (ashwagandha) — a negative-effect primary earns no
    # clinical floor AND no authority floor (not a DRI-essential nutrient).
    payload = score_evidence(
        _product(
            ingredients=[_ingredient(name="Ashwagandha", canonical_id="ashwagandha", quantity=600)],
            matches=[_match(id="INGR_ASHWAGANDHA", ingredient="Ashwagandha",
                            standard_name="Ashwagandha", effect_direction="negative")],
        ),
        apply_primary_floor=True,
    )

    assert payload["score"] == 0.0
    assert "primary_evidence_floor" not in payload["components"]
    assert payload["metadata"]["primary_evidence_floor"] == 0.0


def test_generic_evidence_does_not_import_v3_scorer() -> None:
    import scoring_v4.modules.generic_evidence as ge

    source = Path(ge.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source
