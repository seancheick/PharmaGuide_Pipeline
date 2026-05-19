"""v4 Layer 4 confidence metadata — P1.4 tests."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _ingredient(
    name: str = "Magnesium",
    *,
    canonical_id: str = "magnesium",
    quantity: float = 200.0,
    unit: str = "mg",
    bio_score: float = 14.0,
) -> dict:
    return {
        "name": name,
        "standard_name": name,
        "canonical_id": canonical_id,
        "mapped": bool(canonical_id),
        "bio_score": bio_score,
        "score": bio_score,
        "quantity": quantity,
        "unit": unit,
    }


def _product(**extra) -> dict:
    row = extra.pop("ingredient", _ingredient())
    product = {
        "status": "active",
        "form_factor": "capsule",
        "product_name": "Example Magnesium",
        "brand_name": "Example Brand",
        "supplement_type": {"type": "single_nutrient"},
        "mapped_coverage": 1.0,
        "ingredient_quality_data": {
            "total_active": 1,
            "ingredients_scorable": [row],
            "ingredients": [row],
        },
        "rda_ul_data": {
            "adequacy_results": [
                {"nutrient": row["standard_name"], "pct_rda": 50.0, "pct_ul": 57.0}
            ],
            "safety_flags": [],
        },
        "evidence_data": {
            "clinical_matches": [
                {
                    "id": "study-1",
                    "ingredient": row["standard_name"],
                    "canonical_id": row["canonical_id"],
                    "study_type": "rct_multiple",
                    "evidence_level": "branded-rct",
                    "effect_direction": "positive_strong",
                    "total_enrollment": 250,
                }
            ]
        },
        "contaminant_data": {
            "allergens": {"allergens": []},
            "banned_substances": {"substances": []},
        },
        "compliance_data": {
            "allergen_free_claims": [],
            "gluten_free": False,
            "vegan": False,
            "vegetarian": False,
            "conflicts": [],
            "has_may_contain_warning": False,
        },
        "verified_cert_programs": [
            {"program": "NSF Sport", "scope": "sku", "recency_status": "fresh"}
        ],
        "certification_data": {"gmp": {}, "batch_traceability": {}},
        "proprietary_blends": [],
        "proprietary_data": {"blends": [], "total_active_mg": 200.0, "total_active_ingredients": 1},
    }
    product.update(extra)
    return product


def test_confidence_high_when_evidence_identity_label_and_verification_are_strong() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_product())
    confidence = out["shadow_score_v4_breakdown"]["confidence"]

    assert out["shadow_score_v4_confidence"] == "high"
    assert confidence["band"] == "high"
    assert confidence["score_uncertainty_pts"] == 1
    for key in ("evidence", "label_completeness", "verification", "identity"):
        assert confidence[key]["level"] == "high"
        assert isinstance(confidence[key]["drivers"], list)


def test_confidence_worst_case_rule_lowers_band_for_no_clinical_evidence() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _product(evidence_data={"clinical_matches": []})
    out = score_product_v4_shadow(product)
    confidence = out["shadow_score_v4_breakdown"]["confidence"]

    assert confidence["evidence"]["level"] == "low"
    assert "no_clinical_evidence_matched" in confidence["evidence"]["drivers"]
    assert out["shadow_score_v4_confidence"] == "low"


def test_ingredient_human_underscore_study_types_are_moderate_not_absent() -> None:
    """Regression for P1.4 confidence normalization.

    v3-enriched evidence uses underscore study_type values such as
    systematic_review_meta and rct_multiple. The confidence layer must not
    normalize those into dash forms and then treat human evidence as absent.
    """
    from score_supplements_v4_shadow import score_product_v4_shadow

    for study_type in ("systematic_review_meta", "rct_multiple", "rct_single"):
        product = _product(
            evidence_data={
                "clinical_matches": [
                    {
                        "id": f"study-{study_type}",
                        "ingredient": "Magnesium",
                        "canonical_id": "magnesium",
                        "study_type": study_type,
                        "evidence_level": "ingredient-human",
                        "effect_direction": "positive_strong",
                        "total_enrollment": 250,
                    }
                ]
            }
        )
        out = score_product_v4_shadow(product)
        confidence = out["shadow_score_v4_breakdown"]["confidence"]

        assert confidence["evidence"]["level"] == "moderate"
        assert "product_specific_nct_absent" in confidence["evidence"]["drivers"]
        assert "human_clinical_evidence_absent" not in confidence["evidence"]["drivers"]


def test_no_rda_dose_reference_lowers_confidence_without_zeroing_score() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _product(
        ingredient=_ingredient(
            name="KSM-66 Ashwagandha",
            canonical_id="ashwagandha",
            quantity=600,
            unit="mg",
        ),
        rda_ul_data={
            "adequacy_results": [{"nutrient": "Ashwagandha", "pct_rda": None, "pct_ul": None}],
            "safety_flags": [],
        },
    )
    out = score_product_v4_shadow(product)
    module = out["shadow_score_v4_breakdown"]["module"]
    confidence = out["shadow_score_v4_breakdown"]["confidence"]

    assert module["dimensions"]["dose"]["score"] is None
    assert "dose" in module["metadata"]["excluded_dimensions"]
    assert confidence["label_completeness"]["level"] == "moderate"
    assert "dose_window_not_evaluable_by_rda_proxy" in confidence["label_completeness"]["drivers"]


def test_claimed_cert_without_registry_match_lowers_verification_confidence() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _product(
        verified_cert_programs=[
            {"program": "USP Verified", "scope": "claimed_only", "evidence_source": "product_label"}
        ]
    )
    out = score_product_v4_shadow(product)
    confidence = out["shadow_score_v4_breakdown"]["confidence"]

    assert confidence["verification"]["level"] == "low"
    assert "cert_claimed_only_no_registry_match" in confidence["verification"]["drivers"]
    assert out["shadow_score_v4_confidence"] == "low"


def test_mapped_coverage_between_gate_and_perfect_is_moderate_identity_confidence() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_product(mapped_coverage=0.9))
    confidence = out["shadow_score_v4_breakdown"]["confidence"]

    assert confidence["identity"]["level"] == "moderate"
    assert "mapped_coverage_below_95_percent" in confidence["identity"]["drivers"]
    assert out["shadow_score_v4_confidence"] == "moderate"


def test_blocked_paths_keep_gate_confidence_string_and_skip_confidence_block() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _product(
        contaminant_data={
            "banned_substances": {
                "substances": [
                    {"name": "Vinpocetine", "status": "banned", "match_type": "exact"}
                ]
            }
        }
    )
    out = score_product_v4_shadow(product)

    assert out["shadow_score_v4_confidence"] == "blocked_by_safety_gate"
    assert "confidence" not in out["shadow_score_v4_breakdown"]


def test_confidence_layer_does_not_import_v3_scorer() -> None:
    import scoring_v4.confidence as confidence

    source = Path(confidence.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source
