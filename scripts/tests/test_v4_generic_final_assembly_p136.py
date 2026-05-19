"""v4 Generic final assembly — P1.3.6 tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _ingredient(
    name: str = "Magnesium",
    *,
    standard_name: str | None = None,
    canonical_id: str | None = None,
    bio_score: float = 14.0,
    quantity: float = 200.0,
    unit: str = "mg",
) -> dict:
    return {
        "name": name,
        "standard_name": standard_name or name,
        "canonical_id": canonical_id or (standard_name or name).lower().replace(" ", "_"),
        "mapped": True,
        "bio_score": bio_score,
        "score": bio_score,
        "quantity": quantity,
        "unit": unit,
    }


def _base_product(*, ingredient: dict | None = None, top_level: dict | None = None) -> dict:
    row = ingredient or _ingredient()
    product = {
        "status": "active",
        "form_factor": "capsule",
        "product_name": "Example Product",
        "fullName": "Example Product",
        "brand_name": "Example Brand",
        "supplement_type": {"type": "single_nutrient"},
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
        "clinical_evidence": {"clinical_matches": []},
        "compliance_data": {
            "allergen_free_claims": [],
            "gluten_free": False,
            "vegan": False,
            "vegetarian": False,
            "conflicts": [],
            "has_may_contain_warning": False,
        },
        "contaminant_data": {
            "allergens": {"allergens": []},
            "banned_substances": {"substances": []},
        },
        "certification_data": {
            "gmp": {},
            "batch_traceability": {},
        },
        "verified_cert_programs": [],
        "proprietary_blends": [],
        "proprietary_data": {
            "blends": [],
            "total_active_mg": 200.0,
            "total_active_ingredients": 1,
        },
    }
    if top_level:
        product.update(top_level)
    return product


def _high_quality_product() -> dict:
    product = _base_product(
        top_level={
            "is_trusted_manufacturer": True,
            "claim_physician_formulated": True,
            "manufacturing_region": "USA",
            "has_sustainable_packaging": True,
            "gmp_level": "fda_registered",
            "has_coa": True,
        }
    )
    product["product_name"] = "Thorne Magnesium Bisglycinate"
    product["brand_name"] = "Thorne"
    product["verified_cert_programs"] = [
        {"program": "NSF Sport", "scope": "sku", "recency_status": "fresh"}
    ]
    product["compliance_data"].update(
        {
            "allergen_free_claims": [{"validated": True, "allergen": "gluten"}],
            "gluten_free": True,
            "vegan": False,
            "vegetarian": False,
        }
    )
    return product


def test_manufacturer_trust_scores_d1_d2_and_tail_cap() -> None:
    from scoring_v4.modules.generic import score_generic

    payload = score_generic(_high_quality_product()).to_breakdown()
    trust = payload["manufacturer_trust"]

    assert trust["score"] == 5.0
    assert trust["max"] == 5
    assert trust["components"]["D1_manufacturer_reputation"] == 2.0
    assert trust["components"]["D2_disclosure_quality"] == 1.0
    assert trust["components"]["D3_physician_formulated"] == 0.5
    assert trust["components"]["D4_high_standard_region"] == 1.0
    assert trust["components"]["D5_sustainability"] == 0.5
    assert trust["metadata"]["tail_cap_applied"] is False


def test_mid_tier_manufacturer_evidence_scores_one_without_trusted_brand() -> None:
    from scoring_v4.modules.generic import score_generic

    product = _base_product(
        top_level={
            "certification_data": {"gmp": {"fda_registered": True}, "batch_traceability": {}}
        }
    )
    trust = score_generic(product).to_breakdown()["manufacturer_trust"]

    assert trust["components"]["D1_manufacturer_reputation"] == 1.0
    assert trust["metadata"]["D1_source"] == "mid_tier_verified_evidence"


def test_manufacturer_violations_use_total_deduction_and_apply_default_cap() -> None:
    from scoring_v4.modules.generic import score_generic

    product = _base_product(
        top_level={
            "manufacturer_data": {
                "violations": {
                    "total_deduction_applied": -40.0,
                    "violations": [
                        {"severity_level": "high", "date": "2026-01-01"},
                    ],
                }
            }
        }
    )
    violations = score_generic(product).to_breakdown()["manufacturer_violations"]

    assert violations["score"] == -25.0
    assert violations["floor"] == -25.0
    assert violations["metadata"]["raw_deduction"] == -40.0
    assert violations["metadata"]["cap_applied"] is True


def test_repeat_class_i_violations_use_graduated_cap_for_v3_parity() -> None:
    from scoring_v4.modules.generic import score_generic

    product = _base_product(
        top_level={
            "manufacturer_data": {
                "violations": {
                    "violations": [
                        {"severity_level": "critical", "date": "2026-01-01", "total_deduction": -20.0},
                        {"severity_level": "critical", "date": "2025-10-01", "total_deduction": -20.0},
                        {"severity_level": "critical", "date": "2025-05-01", "total_deduction": -20.0},
                    ]
                }
            }
        }
    )
    violations = score_generic(product).to_breakdown()["manufacturer_violations"]

    assert violations["score"] == -50.0
    assert violations["floor"] == -50.0
    assert violations["metadata"]["class_i_count_3y"] == 3


def test_final_score_assembles_dimensions_plus_manufacturer_adjustments() -> None:
    from scoring_v4.modules.generic import score_generic

    breakdown = score_generic(_high_quality_product()).to_breakdown()

    class_subtotal = breakdown["metadata"]["class_subtotal"]
    raw_score = min(100.0, class_subtotal + 5.0)
    assert class_subtotal > 0
    assert breakdown["manufacturer_trust"]["score"] == 5.0
    assert breakdown["manufacturer_violations"]["score"] == 0.0
    assert breakdown["raw_score_100"] == pytest.approx(raw_score, rel=1e-6)
    assert breakdown["score_100"] == pytest.approx(25.0 + 0.75 * raw_score, rel=1e-6)
    assert breakdown["metadata"]["calibration"]["method"] == "affine_p15"
    assert breakdown["metadata"]["calibration"]["intercept"] == 25.0
    assert breakdown["metadata"]["calibration"]["slope"] == 0.75
    assert breakdown["phase"] == "P1.5_affine_calibration"


def test_not_evaluable_dose_dimension_is_excluded_from_denominator_not_zeroed() -> None:
    from scoring_v4.modules.generic import score_generic

    product = _base_product(
        ingredient=_ingredient(
            name="KSM-66 Ashwagandha",
            standard_name="Ashwagandha",
            canonical_id="ashwagandha",
            bio_score=14,
            quantity=600,
            unit="mg",
        )
    )
    product["rda_ul_data"] = {
        "adequacy_results": [{"nutrient": "Ashwagandha", "pct_rda": None, "pct_ul": None}],
        "safety_flags": [],
    }

    breakdown = score_generic(product).to_breakdown()

    assert breakdown["dimensions"]["dose"]["score"] is None
    assert breakdown["metadata"]["excluded_dimensions"] == ["dose"]
    assert breakdown["metadata"]["evaluable_class_max"] == 75.0
    assert breakdown["raw_score_100"] > breakdown["metadata"]["class_subtotal"], (
        "class subtotal should be rescaled to 100 when dose is not evaluable"
    )
    assert breakdown["score_100"] > breakdown["raw_score_100"], (
        "P1.5 affine calibration should lift compressed scoreable generic rows"
    )


def test_final_score_clamps_after_positive_and_negative_manufacturer_adjustments() -> None:
    from scoring_v4.modules.generic import score_generic

    high = score_generic(_high_quality_product()).to_breakdown()
    assert high["score_100"] <= 100.0

    bad = _high_quality_product()
    bad["manufacturer_data"] = {
        "violations": {"total_deduction_applied": -200.0, "violations": []}
    }
    low = score_generic(bad).to_breakdown()
    assert 0.0 <= low["score_100"] <= 100.0
    assert 0.0 <= low["raw_score_100"] <= 100.0
    assert low["manufacturer_violations"]["score"] == -25.0


def test_p15_affine_calibration_preserves_raw_score_for_audit() -> None:
    from scoring_v4.modules.generic import score_generic

    breakdown = score_generic(_base_product()).to_breakdown()
    raw = breakdown["raw_score_100"]
    calibrated = breakdown["score_100"]

    assert raw is not None
    assert calibrated == pytest.approx(round(25.0 + 0.75 * raw, 1), rel=1e-6)
    assert breakdown["metadata"]["raw_score_100_pre_calibration"] == raw
    assert breakdown["metadata"]["calibration"]["reason"] == "p1_5_canary_score_compression"


def test_shadow_top_level_score_and_verdict_are_populated_for_complete_generic() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_high_quality_product())

    assert out["shadow_score_v4_100"] == out["shadow_score_v4_breakdown"]["module"]["score_100"]
    assert out["shadow_score_v4_100"] is not None
    assert out["shadow_score_v4_verdict"] in {"SAFE", "POOR"}
    assert out["shadow_score_v4_confidence"] in {"high", "moderate", "low"}
    assert out["shadow_score_v4_breakdown"]["confidence"]["band"] == out["shadow_score_v4_confidence"]


def test_shadow_caution_verdict_overrides_safe_score_band() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _high_quality_product()
    product["contaminant_data"]["banned_substances"]["substances"] = [
        {"name": "Watchlist Ingredient", "status": "watchlist", "match_type": "exact"}
    ]

    out = score_product_v4_shadow(product)

    assert out["shadow_score_v4_100"] is not None
    assert out["shadow_score_v4_verdict"] == "CAUTION"


def test_shadow_poor_threshold_is_40_on_v4_100_scale() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _base_product()
    product["manufacturer_data"] = {
        "violations": {"total_deduction_applied": -25.0, "violations": []}
    }

    out = score_product_v4_shadow(product)

    assert out["shadow_score_v4_100"] < 40.0
    assert out["shadow_score_v4_verdict"] == "POOR"


def test_generic_final_assembly_does_not_import_v3_scorer() -> None:
    import scoring_v4.modules.generic as generic

    source = Path(generic.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source
