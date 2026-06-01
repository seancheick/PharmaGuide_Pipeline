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
    hygiene = breakdown["safety_hygiene_base"]["score"]
    # Phase 4: verification bonus is now an additive term (not a denominator dim).
    vbonus = breakdown["verification_bonus"]["score"]
    raw_score = min(100.0, class_subtotal + vbonus + 5.0 + hygiene)
    assert class_subtotal > 0
    assert breakdown["verification_bonus"]["score"] >= 0.0
    assert breakdown["verification_bonus"]["max"] == 8.0
    assert breakdown["manufacturer_trust"]["score"] == 5.0
    assert breakdown["manufacturer_violations"]["score"] == 0.0
    assert hygiene == 4.0  # Phase 5: hygiene cap 10->4
    assert breakdown["metadata"]["safety_hygiene_base_adjustment"] == 4.0
    assert breakdown["metadata"]["verification_bonus_adjustment"] == pytest.approx(vbonus, rel=1e-6)
    # raw_score_100 is rounded to 1dp in the assembler; allow that rounding.
    assert breakdown["raw_score_100"] == pytest.approx(raw_score, abs=0.05)
    assert breakdown["score_100"] == pytest.approx(25.0 + 0.75 * breakdown["raw_score_100"], abs=0.05)
    assert breakdown["metadata"]["calibration"]["method"] == "affine_p15"
    assert breakdown["metadata"]["calibration"]["intercept"] == 25.0
    assert breakdown["metadata"]["calibration"]["slope"] == 0.75
    assert breakdown["phase"] == "P1.5_affine_calibration"


def test_quantified_no_rda_dose_gets_partial_credit_not_excluded() -> None:
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

    # Phase 6: a recognized botanical with a quantified dose now scores via the
    # clinical therapeutic-range adapter (ashwagandha 250-600; 600mg in range),
    # not the old RDA-proxy partial credit. Never excluded from the denominator.
    dose = breakdown["dimensions"]["dose"]
    assert dose["score"] == 21.0
    assert dose["metadata"]["method"] == "botanical_clinical_dose_v1"
    assert dose["metadata"]["botanical_dose_band"] == "within_studied_range"
    assert breakdown["metadata"]["excluded_dimensions"] == []
    # Phase 4: core (form+dose+evid+transp) sums to 85; trust dim removed.
    assert breakdown["metadata"]["evaluable_class_max"] == 85.0
    assert breakdown["score_100"] > breakdown["raw_score_100"], (
        "P1.5 affine calibration should lift compressed scoreable generic rows"
    )


def test_missing_dose_dimension_is_still_excluded_when_no_quantified_evidence() -> None:
    from scoring_v4.modules.generic import score_generic

    product = _base_product(
        ingredient=_ingredient(
            name="Undisclosed Botanical",
            standard_name="Botanical",
            canonical_id="botanical",
            bio_score=10,
            quantity=0,
            unit="",
        )
    )
    product["rda_ul_data"] = {"adequacy_results": [], "safety_flags": []}

    breakdown = score_generic(product).to_breakdown()

    assert breakdown["dimensions"]["dose"]["score"] is None
    assert breakdown["metadata"]["excluded_dimensions"] == ["dose"]


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

    # A -25 manufacturer violation is a weak profile: POOR. Post-Phase-4/5 the
    # POOR comes from the RAW floor (raw < 40), not the calibrated score — the
    # affine lift can leave the displayed score >=40 while raw stays weak.
    assert out["shadow_score_v4_breakdown"]["module"]["raw_score_100"] < 40.0
    assert out["shadow_score_v4_verdict"] == "POOR"


def test_shadow_verdict_uses_raw_floor_not_affine_lift_alone() -> None:
    from score_supplements_v4_shadow import _verdict_from_score

    assert _verdict_from_score(48.2, raw_score_100=31.0) == "POOR"
    assert _verdict_from_score(48.2, raw_score_100=40.0) == "SAFE"


def test_safety_hygiene_base_is_zero_for_hard_cleanliness_failure() -> None:
    # Phase 5: hard cleanliness failure is gated only on banned/recalled signals
    # (a manufacturer violation no longer zeros hygiene — it's penalised by its
    # own dimension, so zeroing here too would double-penalise).
    from scoring_v4.modules.generic import score_generic

    product = _base_product()
    product["contaminant_data"]["banned_substances"]["substances"] = [
        {"name": "Banned Ingredient", "status": "banned", "match_type": "exact"}
    ]

    hygiene = score_generic(product).to_breakdown()["safety_hygiene_base"]

    assert hygiene["score"] == 0.0
    assert "banned_high_risk_or_watchlist_match_present" in hygiene["failed_components"]
    assert hygiene["metadata"]["hard_cleanliness_failure"] is True


def test_manufacturer_violation_no_longer_zeros_hygiene() -> None:
    # Phase 5 anti-double-penalty: a manufacturer violation is docked by the
    # manufacturer_violations dimension; hygiene still credits the clean axes.
    from scoring_v4.modules.generic import score_generic

    product = _base_product()
    product["manufacturer_data"] = {
        "violations": {"total_deduction_applied": -25.0, "violations": []}
    }

    hygiene = score_generic(product).to_breakdown()["safety_hygiene_base"]
    assert hygiene["score"] == 4.0
    assert hygiene["metadata"].get("hard_cleanliness_failure") is not True


def test_generic_final_assembly_does_not_import_v3_scorer() -> None:
    import scoring_v4.modules.generic as generic

    source = Path(generic.__file__).read_text()
    assert "from score_supplements" not in source
    assert "import score_supplements" not in source


# --- Phase 4 anti-regression: Trust → Verification Bonus -------------------

def test_no_cert_product_keeps_full_core_no_15pt_penalty() -> None:
    # The whole point of Phase 4: an uncertified clean product loses NOTHING in
    # the denominator. Its core is identical to a verified product's core; only
    # the additive bonus differs.
    from scoring_v4.modules.generic import score_generic

    no_cert = score_generic(_base_product()).to_breakdown()
    assert no_cert["verification_bonus"]["score"] == 0.0
    # core sum is unaffected by the (absent) verification signal
    assert no_cert["metadata"]["evaluable_class_max"] == 85.0
    assert "trust" not in no_cert["dimensions"]


def test_verified_product_core_equals_uncertified_core() -> None:
    # Same formulation, differ only in certs → identical core, bonus differs.
    from scoring_v4.modules.generic import score_generic

    plain = score_generic(_base_product()).to_breakdown()
    verified = score_generic(_high_quality_product()).to_breakdown()
    # _high_quality_product differs in brand/cert/compliance; isolate the bonus:
    assert verified["verification_bonus"]["score"] >= plain["verification_bonus"]["score"]
    assert verified["verification_bonus"]["score"] <= 8.0


def test_assembly_does_not_renormalize_core_to_100() -> None:
    # No hidden (sum/evaluable_max)*100. core_class_max must be the native 85,
    # and a product with an excluded dimension is NOT scaled up.
    from scoring_v4.modules.generic import score_generic

    product = _base_product(
        ingredient=_ingredient(
            name="Undisclosed Botanical", standard_name="Botanical",
            canonical_id="botanical", bio_score=10, quantity=0, unit="",
        )
    )
    product["rda_ul_data"] = {"adequacy_results": [], "safety_flags": []}
    breakdown = score_generic(product).to_breakdown()

    assert breakdown["metadata"]["excluded_dimensions"] == ["dose"]
    # core_class_max excludes the None dose dim (85 - 25 = 60) and the score is
    # the NATIVE sum of the evaluable dims, never divided/scaled back up to 100.
    assert breakdown["metadata"]["evaluable_class_max"] == 60.0
    core_sum = breakdown["metadata"]["raw_dimension_sum"]
    assert core_sum <= 60.0  # native, not renormalized to a 100 base


def test_score_cannot_exceed_100() -> None:
    from scoring_v4.modules.generic import score_generic

    breakdown = score_generic(_high_quality_product()).to_breakdown()
    assert breakdown["raw_score_100"] <= 100.0
    assert breakdown["score_100"] <= 100.0


def test_botanical_no_dose_scores_zero_not_excluded_not_floored() -> None:
    # Phase 6 supersedes the Phase-4 floor guard: a botanical with no disclosed
    # dose now scores the dose dimension as a real 0 (honest quality gap), not
    # None (excluded) and not floored. The botanical_dose_deferred flag stays off.
    from scoring_v4.modules.generic import score_generic

    product = _base_product(
        ingredient=_ingredient(
            name="Ashwagandha", standard_name="Ashwagandha",
            canonical_id="ashwagandha", bio_score=8, quantity=0, unit="",
        )
    )
    product["primary_type"] = "herbal_botanical"
    product["rda_ul_data"] = {"adequacy_results": [], "safety_flags": []}
    breakdown = score_generic(product).to_breakdown()

    assert breakdown["dimensions"]["dose"]["score"] == 0.0
    assert breakdown["metadata"]["excluded_dimensions"] == []
    assert breakdown["metadata"]["botanical_dose_deferred"] is False
    assert breakdown["metadata"]["botanical_raw_floor_applied"] is False


def test_non_botanical_none_dose_is_not_floored() -> None:
    # The guard is botanical-only: a single_nutrient with None dose is NOT floored.
    from scoring_v4.modules.generic import score_generic

    product = _base_product(
        ingredient=_ingredient(
            name="Undisclosed", standard_name="Mystery", canonical_id="mystery",
            bio_score=8, quantity=0, unit="",
        )
    )
    product["rda_ul_data"] = {"adequacy_results": [], "safety_flags": []}
    breakdown = score_generic(product).to_breakdown()

    assert breakdown["metadata"]["botanical_dose_deferred"] is False
    assert breakdown["metadata"]["botanical_raw_floor_applied"] is False
