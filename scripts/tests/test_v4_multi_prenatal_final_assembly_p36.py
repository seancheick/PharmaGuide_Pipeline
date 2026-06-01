"""v4 P3.6 — multi/prenatal final assembly tests.

Closes the multi/prenatal module by wiring:

  - Manufacturer Trust (+0..+5)
  - Manufacturer Violations (0..negative cap)
  - raw_score_100 assembly
  - Phase 9 rubric-is-score policy (`score_100 = raw`)
  - shadow scorer score / verdict / confidence output
"""

from __future__ import annotations

from datetime import date
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _ingredient(
    canonical_id: str,
    *,
    name: str | None = None,
    quantity: float = 100.0,
    unit: str = "mg",
    bio_score: float = 10.0,
    matched_form: str | None = None,
) -> dict:
    return {
        "name": name or canonical_id.replace("_", " ").title(),
        "standard_name": name or canonical_id.replace("_", " ").title(),
        "canonical_id": canonical_id,
        "mapped": True,
        "quantity": quantity,
        "unit": unit,
        "bio_score": bio_score,
        "score": bio_score,
        "matched_form": matched_form or "",
    }


def _panel() -> list[dict]:
    return [
        _ingredient("vitamin_a", name="Vitamin A", quantity=900, unit="mcg RAE"),
        _ingredient("vitamin_c", name="Vitamin C", quantity=90, unit="mg"),
        _ingredient("vitamin_d", name="Vitamin D", quantity=25, unit="mcg", matched_form="Cholecalciferol D3"),
        _ingredient("vitamin_e", name="Vitamin E", quantity=15, unit="mg"),
        _ingredient("vitamin_b9_folate", name="Folate", quantity=400, unit="mcg DFE", matched_form="Methylfolate"),
        _ingredient("vitamin_b12_cobalamin", name="Vitamin B12", quantity=50, unit="mcg", matched_form="Methylcobalamin"),
        _ingredient("zinc", name="Zinc", quantity=11, unit="mg", matched_form="Zinc bisglycinate"),
        _ingredient("iodine", name="Iodine", quantity=150, unit="mcg"),
    ]


def _adequacy_rows() -> list[dict]:
    return [
        {"nutrient": "Vitamin A", "pct_rda": 100, "pct_ul": 30},
        {"nutrient": "Vitamin C", "pct_rda": 100, "pct_ul": 20},
        {"nutrient": "Vitamin D", "pct_rda": 125, "pct_ul": 25},
        {"nutrient": "Vitamin E", "pct_rda": 100, "pct_ul": 10},
        {"nutrient": "Folate", "pct_rda": 100, "pct_ul": 40},
        {"nutrient": "Vitamin B12", "pct_rda": 200, "pct_ul": None},
        {"nutrient": "Zinc", "pct_rda": 100, "pct_ul": 25},
        {"nutrient": "Iodine", "pct_rda": 100, "pct_ul": 30},
    ]


def _clinical_match() -> dict:
    return {
        "ingredient": "Vitamin D",
        "standard_name": "Vitamin D",
        "study_name": "Vitamin D",
        "study_type": "systematic_review_meta",
        "evidence_level": "ingredient-human",
        "effect_direction": "positive_strong",
        "total_enrollment": 1500,
    }


def _multi_product(
    *,
    trust_certs: list[dict] | None = None,
    gmp: dict | None = None,
    has_disease_claims: bool = False,
    is_trusted_manufacturer: bool = False,
    manufacturing_region: str = "",
    critical_violations: int = 0,
    top_level: dict | None = None,
) -> dict:
    product = {
        "status": "active",
        "form_factor": "tablet",
        "product_name": "Complete Prenatal Multivitamin",
        "fullName": "Complete Prenatal Multivitamin",
        "brand_name": "Example Brand",
        "supplement_type": {"type": "multivitamin"},
        "primary_category": "multivitamin",
        "ingredient_quality_data": {
            "total_active": 8,
            "ingredients_scorable": _panel(),
        },
        "rda_ul_data": {
            "adequacy_results": _adequacy_rows(),
            "safety_flags": [],
        },
        "evidence_data": {"clinical_matches": [_clinical_match()]},
        "clinical_evidence": {"clinical_matches": [_clinical_match()]},
        "verified_cert_programs": trust_certs or [],
        "certification_data": {
            "gmp": gmp or {},
            "batch_traceability": {},
        },
        "compliance_data": {
            "gluten_free": True,
            "allergen_free_claims": ["dairy-free"],
            "vegan": False,
            "vegetarian": False,
            "conflicts": [],
            "has_may_contain_warning": False,
        },
        "contaminant_data": {
            "allergens": {"allergens": []},
            "banned_substances": {"substances": []},
        },
        "proprietary_blends": [],
        "proprietary_data": {
            "blends": [],
            "total_active_mg": 1200,
            "total_active_ingredients": 8,
        },
        "has_disease_claims": has_disease_claims,
        "is_trusted_manufacturer": is_trusted_manufacturer,
        "manufacturing_region": manufacturing_region,
    }
    if critical_violations:
        product["manufacturer_data"] = {
            "violations": {
                "total_deduction_applied": -25.0 * critical_violations,
                "violations": [
                    {
                        "severity_level": "critical",
                        "date": date.today().isoformat(),
                        "total_deduction": -25.0,
                    }
                    for _ in range(critical_violations)
                ],
            }
        }
    if top_level:
        product.update(top_level)
    return product


def test_multi_prenatal_score_100_assembled_at_p36() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(_multi_product()).to_breakdown()

    assert breakdown["raw_score_100"] is not None
    assert breakdown["score_100"] is not None
    assert 0.0 <= breakdown["raw_score_100"] <= 100.0
    assert 0.0 <= breakdown["score_100"] <= 100.0
    assert breakdown["phase"] == "P3.6_multi_prenatal_final_assembly"


def test_multi_prenatal_rubric_score_policy_applied() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(_multi_product()).to_breakdown()
    raw = breakdown["raw_score_100"]
    expected = round(max(0.0, min(100.0, 1.0 * raw)), 1)

    assert breakdown["score_100"] == expected
    assert breakdown["metadata"]["score_policy"]["method"] == "rubric_raw_is_production_score"


def test_multi_prenatal_raw_score_sums_dimensions_and_manufacturer_adjustments() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(_multi_product(
        is_trusted_manufacturer=True,
        manufacturing_region="usa",
    )).to_breakdown()

    dimension_sum = sum(
        dim["score"] for dim in breakdown["dimensions"].values()
        if dim["score"] is not None
    )
    expected_raw = min(
        100.0,
        dimension_sum
        + breakdown["verification_bonus"]["score"]  # Phase 4 additive term
        + breakdown["manufacturer_trust"]["score"]
        + breakdown["manufacturer_violations"]["score"]
        + breakdown["safety_hygiene_base"]["score"],
    )

    # Phase 4: trust removed from the denominator → 4 core dims sum to 85.
    assert breakdown["metadata"]["evaluable_class_max"] == 85.0
    assert breakdown["metadata"]["excluded_dimensions"] == []
    assert breakdown["metadata"]["safety_hygiene_base_adjustment"] == breakdown["safety_hygiene_base"]["score"]
    assert breakdown["raw_score_100"] == round(expected_raw, 1)
    assert breakdown["metadata"]["manufacturer_trust_adjustment"] > 0


def test_multi_prenatal_manufacturer_violations_drag_score_down() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    base = score_multi_prenatal(_multi_product()).to_breakdown()
    flagged = score_multi_prenatal(_multi_product(critical_violations=1)).to_breakdown()

    assert flagged["manufacturer_violations"]["score"] < 0.0
    assert flagged["raw_score_100"] < base["raw_score_100"]


def test_multi_prenatal_repeat_class_i_violations_use_graduated_cap() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(_multi_product(critical_violations=3)).to_breakdown()

    assert breakdown["manufacturer_violations"]["score"] == -50.0
    assert breakdown["manufacturer_violations"]["floor"] == -50.0
    assert breakdown["manufacturer_violations"]["metadata"]["class_i_count_3y"] == 3


def test_multi_prenatal_score_clamps_between_zero_and_100() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    high = score_multi_prenatal(_multi_product(
        trust_certs=[
            {"program": "NSF Certified for Sport", "scope": "sku", "evidence_source": "registry"},
            {"program": "USP Verified", "scope": "sku", "evidence_source": "registry"},
            {"program": "Informed Choice", "scope": "sku", "evidence_source": "registry"},
        ],
        gmp={"nsf_gmp": True},
        is_trusted_manufacturer=True,
        manufacturing_region="usa",
        top_level={"has_coa": True, "has_batch_lookup": True},
    )).to_breakdown()
    low = score_multi_prenatal(_multi_product(critical_violations=3)).to_breakdown()

    assert 0.0 <= high["raw_score_100"] <= 100.0
    assert 0.0 <= high["score_100"] <= 100.0
    assert 0.0 <= low["raw_score_100"] <= 100.0
    assert 0.0 <= low["score_100"] <= 100.0


def test_shadow_emits_real_score_verdict_and_confidence_for_multi_prenatal() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_multi_product())

    assert out["shadow_score_v4_module"] == "multi_or_prenatal"
    assert out["shadow_score_v4_100"] is not None
    assert out["shadow_score_v4_verdict"] in {"SAFE", "POOR", "CAUTION"}
    assert out["shadow_score_v4_confidence"] in {"high", "moderate", "low"}
    assert "confidence" in out["shadow_score_v4_breakdown"]


def test_shadow_caution_carried_from_safety_gate_overrides_score_band() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    out = score_product_v4_shadow(_multi_product(has_disease_claims=True))

    assert out["shadow_score_v4_100"] is not None
    assert out["shadow_score_v4_verdict"] == "CAUTION"


def test_shadow_blocked_safety_short_circuits_before_p36() -> None:
    from score_supplements_v4_shadow import score_product_v4_shadow

    product = _multi_product()
    product["contaminant_data"] = {
        "banned_substances": {
            "substances": [
                {"name": "DMAA", "status": "banned", "match_type": "exact"},
            ]
        }
    }
    out = score_product_v4_shadow(product)

    assert out["shadow_score_v4_verdict"] == "BLOCKED"
    assert out["shadow_score_v4_100"] is None
    assert out["shadow_score_v4_confidence"] == "blocked_by_safety_gate"


def test_multi_prenatal_final_assembly_does_not_import_v3_scorer() -> None:
    import ast

    source_path = SCRIPTS_ROOT / "scoring_v4" / "modules" / "multi_prenatal.py"
    tree = ast.parse(source_path.read_text())

    forbidden = {"score_supplements", "score_supplements_v3"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name in forbidden for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden
