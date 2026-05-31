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
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_product())

    evidence = out["shadow_score_v4_breakdown"]["module"]["dimensions"]["evidence"]
    assert evidence["score"] == 6.48
    assert evidence["max"] == 20.0
    assert evidence["metadata"]["phase"] == "P1.3.3_evidence_pipeline"


def test_generic_evidence_does_not_import_v3_scorer() -> None:
    import scoring_v4.modules.generic_evidence as ge

    source = Path(ge.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source
