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
    from score_supplements_v4 import score_product_v4

    out = score_product_v4(_product())
    confidence = out["v4_breakdown"]["confidence"]

    assert out["v4_confidence"] == "high"
    assert confidence["band"] == "high"
    assert confidence["score_uncertainty_pts"] == 1
    for key in ("evidence", "label_completeness", "verification", "identity"):
        assert confidence[key]["level"] == "high"
        assert isinstance(confidence[key]["drivers"], list)


def test_confidence_worst_case_rule_lowers_band_for_no_scored_evidence() -> None:
    from score_supplements_v4 import score_product_v4

    product = _product(
        ingredient=_ingredient(name="MSM", canonical_id="msm"),
        evidence_data={"clinical_matches": []},
        rda_ul_data={
            "adequacy_results": [{"nutrient": "MSM", "pct_rda": None, "pct_ul": None}],
            "safety_flags": [],
        },
    )
    out = score_product_v4(product)
    confidence = out["v4_breakdown"]["confidence"]

    assert confidence["evidence"]["level"] == "low"
    assert "no_clinical_evidence_matched" in confidence["evidence"]["drivers"]
    assert out["v4_confidence"] == "low"


def test_module_owned_evidence_floor_is_moderate_not_absent() -> None:
    from score_supplements_v4 import score_product_v4

    product = _product(evidence_data={"clinical_matches": []})
    out = score_product_v4(product)
    confidence = out["v4_breakdown"]["confidence"]

    assert out["v4_breakdown"]["module"]["dimensions"]["evidence"]["score"] == 10.0
    assert confidence["evidence"]["level"] == "moderate"
    assert "nutrition_authority_evidence_floor" in confidence["evidence"]["drivers"]
    assert "no_clinical_evidence_matched" not in confidence["evidence"]["drivers"]
    assert out["v4_confidence"] == "moderate"


def test_module_recovered_clinical_contract_evidence_is_moderate_not_absent() -> None:
    from score_supplements_v4 import score_product_v4

    product = _product(
        ingredient=_ingredient(name="Coenzyme Q10", canonical_id="coq10"),
        evidence_data={"clinical_matches": []},
        rda_ul_data={
            "adequacy_results": [
                {"nutrient": "Coenzyme Q10", "pct_rda": None, "pct_ul": None}
            ],
            "safety_flags": [],
        },
    )
    out = score_product_v4(product)
    confidence = out["v4_breakdown"]["confidence"]

    assert out["v4_breakdown"]["module"]["dimensions"]["evidence"]["score"] >= 14.0
    assert confidence["evidence"]["level"] == "moderate"
    assert "v4_evidence_recovered_from_contract" in confidence["evidence"]["drivers"]
    assert "human_clinical_evidence_absent" not in confidence["evidence"]["drivers"]
    assert out["v4_confidence"] == "moderate"


def test_missing_primary_dose_scores_but_lowers_label_confidence() -> None:
    from score_supplements_v4 import score_product_v4

    product = _product(ingredient=_ingredient(quantity=0.0, unit="NP"))
    out = score_product_v4(product)
    confidence = out["v4_breakdown"]["confidence"]
    completeness = out["v4_breakdown"]["completeness_gate"]

    assert out["v4_verdict"] != "NOT_SCORED"
    assert "dose_not_disclosed" in completeness["soft_missing"]
    assert completeness["score_cap"] is None
    assert completeness["verdict_ceiling"] is None
    assert confidence["label_completeness"]["level"] == "low"
    assert "dose_not_disclosed" in confidence["label_completeness"]["drivers"]


def test_ingredient_human_underscore_study_types_are_moderate_not_absent() -> None:
    """Regression for P1.4 confidence normalization.

    v3-enriched evidence uses underscore study_type values such as
    systematic_review_meta and rct_multiple. The confidence layer must not
    normalize those into dash forms and then treat human evidence as absent.
    """
    from score_supplements_v4 import score_product_v4

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
        out = score_product_v4(product)
        confidence = out["v4_breakdown"]["confidence"]

        assert confidence["evidence"]["level"] == "moderate"
        assert "product_specific_nct_absent" in confidence["evidence"]["drivers"]
        assert "human_clinical_evidence_absent" not in confidence["evidence"]["drivers"]


def test_no_rda_dose_reference_lowers_confidence_without_zeroing_score() -> None:
    from score_supplements_v4 import score_product_v4

    # Non-botanical no-RDA ingredient (CoQ10): exercises the GENERIC
    # supplemental-window proxy + its confidence downgrade. Botanicals now
    # route to the clinical-dose path (Phase 6) so they no longer hit this
    # generic no-RDA branch — use a non-botanical to keep testing it.
    product = _product(
        ingredient=_ingredient(
            name="Coenzyme Q10",
            canonical_id="coq10",
            quantity=200,
            unit="mg",
        ),
        rda_ul_data={
            "adequacy_results": [{"nutrient": "Coenzyme Q10", "pct_rda": None, "pct_ul": None}],
            "safety_flags": [],
        },
    )
    out = score_product_v4(product)
    module = out["v4_breakdown"]["module"]
    confidence = out["v4_breakdown"]["confidence"]

    assert module["dimensions"]["dose"]["score"] == 16.0
    assert "dose" not in module["metadata"]["excluded_dimensions"]
    assert confidence["label_completeness"]["level"] == "moderate"
    assert "dose_window_partial_without_rda_reference" in confidence["label_completeness"]["drivers"]


def test_claimed_cert_without_registry_match_is_moderate_verification_confidence() -> None:
    from score_supplements_v4 import score_product_v4

    product = _product(
        verified_cert_programs=[
            {"program": "USP Verified", "scope": "claimed_only", "evidence_source": "product_label"}
        ]
    )
    out = score_product_v4(product)
    confidence = out["v4_breakdown"]["confidence"]

    assert confidence["verification"]["level"] == "moderate"
    assert "cert_claimed_only_no_registry_match" in confidence["verification"]["drivers"]
    assert out["v4_confidence"] == "moderate"


def test_cross_brand_sku_cert_is_ignored_for_verification_confidence() -> None:
    from score_supplements_v4 import score_product_v4

    product = _product(
        brand_name="CVS Health",
        verified_cert_programs=[
            {
                "program": "NSF Sport",
                "scope": "sku",
                "recency_status": "fresh",
                "matched_brand": "LTH",
                "matched_product": "GLOW Omega-3 Fish Oil",
            }
        ],
    )
    out = score_product_v4(product)
    confidence = out["v4_breakdown"]["confidence"]

    assert confidence["verification"]["level"] == "moderate"
    assert "cert_brand_mismatch_ignored" in confidence["verification"]["drivers"]
    assert "cert_sku_verified" not in confidence["verification"]["drivers"]
    assert out["v4_confidence"] == "moderate"


def test_verified_cert_dominates_secondary_claimed_only_cert_confidence() -> None:
    """Regression: products can carry one real SKU cert plus another label claim
    whose registry match was absent. The unresolved secondary claim must not drag
    a genuinely SKU-verified product's verification confidence to low."""
    from score_supplements_v4 import score_product_v4

    product = _product(
        verified_cert_programs=[
            {"program": "NSF Sport", "scope": "sku", "recency_status": "fresh"},
            {"program": "USP Verified", "scope": "claimed_only"},
        ]
    )
    out = score_product_v4(product)
    confidence = out["v4_breakdown"]["confidence"]

    assert confidence["verification"]["level"] == "high"
    assert "cert_sku_verified" in confidence["verification"]["drivers"]
    assert out["v4_confidence"] == "high"


def test_mapped_coverage_between_gate_and_perfect_is_moderate_identity_confidence() -> None:
    from score_supplements_v4 import score_product_v4

    rows = [_ingredient(name=f"Nutrient {i}", canonical_id=f"nutrient_{i}") for i in range(9)]
    rows.append(_ingredient(name="Unmapped", canonical_id=""))
    product = _product(mapped_coverage=0.9)
    product["ingredient_quality_data"]["ingredients_scorable"] = rows
    product["ingredient_quality_data"]["ingredients"] = rows
    out = score_product_v4(product)
    confidence = out["v4_breakdown"]["confidence"]

    assert confidence["identity"]["level"] == "moderate"
    assert "mapped_coverage_below_95_percent" in confidence["identity"]["drivers"]
    assert out["v4_confidence"] == "moderate"


def test_zero_dose_epa_dha_placeholders_do_not_lower_identity_confidence() -> None:
    from score_supplements_v4 import score_product_v4

    rows = [
        _ingredient(name="Fish Oil", canonical_id="fish_oil", quantity=2000, unit="mg"),
        _ingredient(name="EPA", canonical_id="epa", quantity=0, unit="NP", bio_score=0),
        _ingredient(name="DHA", canonical_id="dha", quantity=0, unit="NP", bio_score=0),
    ]
    rows[1]["identity_confidence"] = 0.0
    rows[2]["identity_confidence"] = 0.0
    product = _product(ingredient=rows[0])
    product["ingredient_quality_data"]["ingredients_scorable"] = rows
    product["ingredient_quality_data"]["ingredients"] = rows

    out = score_product_v4(product)
    confidence = out["v4_breakdown"]["confidence"]

    assert confidence["identity"]["level"] == "high"
    assert "ingredient_identity_confidence_below_80_percent" not in confidence["identity"]["drivers"]


def test_conservative_blend_anchor_mass_is_moderate_label_confidence() -> None:
    from scoring_v4.confidence import evaluate_confidence

    confidence = evaluate_confidence(
        _product(),
        module_breakdown={"dimensions": {}},
        safety_gate={},
        completeness_gate={"soft_missing": ["conservative_blend_anchor_mass"]},
    )

    assert confidence["label_completeness"]["level"] == "moderate"
    assert "conservative_blend_anchor_mass" in confidence["label_completeness"]["drivers"]


def test_blocked_paths_keep_gate_confidence_string_and_skip_confidence_block() -> None:
    from score_supplements_v4 import score_product_v4

    product = _product(
        contaminant_data={
            "banned_substances": {
                "substances": [
                    {"name": "Vinpocetine", "status": "banned", "match_type": "exact"}
                ]
            }
        }
    )
    out = score_product_v4(product)

    assert out["v4_confidence"] == "blocked_by_safety_gate"
    assert "confidence" not in out["v4_breakdown"]


def test_confidence_layer_does_not_import_v3_scorer() -> None:
    import scoring_v4.confidence as confidence

    source = Path(confidence.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source
