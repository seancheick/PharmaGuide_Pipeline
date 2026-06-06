"""v4 P3.2 — multi/prenatal Dose dimension tests."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _adequacy(
    nutrient: str,
    *,
    pct_rda: float | None = 100.0,
    pct_ul: float | None = 20.0,
    scoring_eligible: bool = True,
) -> dict:
    return {
        "nutrient": nutrient,
        "pct_rda": pct_rda,
        "pct_ul": pct_ul,
        "scoring_eligible": scoring_eligible,
    }


def _ingredient(
    canonical_id: str,
    *,
    name: str | None = None,
    quantity: float = 10.0,
    unit: str = "mg",
    bio_score: float | None = None,
) -> dict:
    row = {
        "name": name or canonical_id.replace("_", " ").title(),
        "canonical_id": canonical_id,
        "mapped": True,
        "quantity": quantity,
        "unit": unit,
    }
    if bio_score is not None:
        row["bio_score"] = bio_score
    return row


def _product(*, name: str = "Complete Multivitamin", adequacy_results=None, safety_flags=None, ingredients=None) -> dict:
    return {
        "status": "active",
        "form_factor": "tablet",
        "product_name": name,
        "supplement_type": {"type": "multivitamin"},
        "primary_category": "multivitamin",
        "ingredient_quality_data": {
            "total_active": len(ingredients or []),
            "ingredients_scorable": list(ingredients or []),
        },
        "rda_ul_data": {
            "adequacy_results": list(adequacy_results or []),
            "safety_flags": list(safety_flags or []),
        },
    }


CORE_ANCHORS = [
    "Vitamin A",
    "Vitamin C",
    "Vitamin D",
    "Folate",
    "Vitamin B12",
    "Zinc",
]


PRENATAL_CORE = [
    "Folate",
    "Iron",
    "Iodine",
    "Vitamin D",
    "Vitamin B12",
]


def test_dose_payload_shape_and_phase() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(adequacy_results=[_adequacy(n) for n in CORE_ANCHORS]))

    assert set(payload.keys()) == {"score", "max", "components", "penalties", "metadata"}
    assert payload["max"] == 30.0
    assert payload["metadata"]["phase"] == "P3.2_multi_prenatal_dose"
    assert payload["score"] <= 30.0


def test_rda_ai_coverage_full_credit_for_50_to_200_pct_rda_under_ul() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(adequacy_results=[
        _adequacy("Vitamin C", pct_rda=50, pct_ul=5),
        _adequacy("Vitamin D", pct_rda=100, pct_ul=25),
        _adequacy("Vitamin B12", pct_rda=200, pct_ul=None),
    ]))

    assert payload["components"]["rda_ai_coverage"] == 20.0
    assert payload["metadata"]["coverage_nutrient_count"] == 3


def test_rda_ai_coverage_is_proportional_below_half_rda() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(adequacy_results=[
        _adequacy("Vitamin D", pct_rda=25, pct_ul=5),
        _adequacy("Zinc", pct_rda=10, pct_ul=3),
    ]))

    # pct_rda 25 => 0.50 credit; pct_rda 10 => 0.20 credit; avg=.35*20=7
    assert payload["components"]["rda_ai_coverage"] == 7.0


def test_high_b_vitamin_without_ul_is_softly_downweighted_not_zeroed() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(adequacy_results=[
        _adequacy("Vitamin B1 (Thiamine)", pct_rda=4000, pct_ul=None),
    ]))

    assert payload["components"]["rda_ai_coverage"] == 13.0
    assert payload["metadata"]["coverage_nutrient_scores"]["vitamin_b1_thiamine"] == 0.65


def test_over_ul_but_below_b7_threshold_gets_partial_credit_without_penalty() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(adequacy_results=[
        _adequacy("Niacin", pct_rda=300, pct_ul=120),
    ]))

    assert payload["components"]["rda_ai_coverage"] == 10.0
    assert payload["penalties"]["B7_dose_safety"] == -0.0


def test_b7_penalty_caps_at_three_and_zeroes_over_150_ul_coverage() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(
        adequacy_results=[
            _adequacy("Niacin", pct_rda=400, pct_ul=180),
            _adequacy("Iron", pct_rda=300, pct_ul=220),
        ],
        safety_flags=[
            {"nutrient": "Niacin", "pct_ul": 180},
            {"nutrient": "Iron", "pct_ul": 220},
        ],
    ))

    assert payload["components"]["rda_ai_coverage"] == 0.0
    assert payload["penalties"]["B7_dose_safety"] == -3.0
    assert payload["score"] == 0.0


def test_panel_breadth_scales_to_five_points_at_eighteen_nutrients() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    nutrients = [f"Nutrient {i}" for i in range(18)]
    payload = score_dose(_product(adequacy_results=[_adequacy(n) for n in nutrients]))

    assert payload["components"]["panel_breadth"] == 5.0
    assert payload["metadata"]["panel_breadth_count"] == 18


def test_general_multi_core_anchor_coverage_uses_non_prenatal_anchor_set() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(
        name="Men's Complete Multivitamin",
        adequacy_results=[_adequacy(n) for n in CORE_ANCHORS],
    ))

    assert payload["components"]["critical_nutrient_coverage"] == 5.0
    assert payload["metadata"]["critical_nutrient_mode"] == "core_multi"
    assert payload["metadata"]["critical_nutrients_missing"] == []


def test_prenatal_core_coverage_does_not_require_choline_or_dha() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(
        name="Complete Prenatal",
        adequacy_results=[_adequacy(n, pct_rda=60) for n in PRENATAL_CORE],
        ingredients=[],
    ))

    assert payload["components"]["critical_nutrient_coverage"] == 5.0
    assert payload["metadata"]["critical_nutrient_mode"] == "prenatal"
    assert payload["metadata"]["critical_nutrients_missing"] == []
    assert payload["metadata"]["prenatal_complement_scores"] == {"choline": 0.0, "dha": 0.0}
    assert "prenatal_complement_support" not in payload["components"]


def test_prenatal_critical_thresholds_are_not_downgraded_by_form_bio_weighting() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(
        name="Complete Prenatal with DHA",
        adequacy_results=[_adequacy(n, pct_rda=60) for n in PRENATAL_CORE],
        ingredients=[
            _ingredient("folate", name="Folate", bio_score=3),
            _ingredient("iron", name="Iron", bio_score=3),
            _ingredient("iodine", name="Iodine", bio_score=3),
            _ingredient("vitamin_d", name="Vitamin D", bio_score=3),
            _ingredient("vitamin_b12", name="Vitamin B12", bio_score=3),
            _ingredient("dha", name="DHA", quantity=200, unit="mg"),
        ],
    ))

    assert payload["metadata"]["critical_nutrient_scores"] == {
        "folate": 1.0,
        "iodine": 1.0,
        "iron": 1.0,
        "vitamin_b12": 1.0,
        "vitamin_d": 1.0,
    }
    assert payload["components"]["critical_nutrient_coverage"] == 5.0


def test_prenatal_dha_half_credit_at_100mg_and_missing_list_records_gaps() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(
        name="Prenatal Multi",
        adequacy_results=[
            _adequacy("Folate", pct_rda=60),
            _adequacy("Iron", pct_rda=60),
        ],
        ingredients=[_ingredient("dha", name="DHA", quantity=100, unit="mg")],
    ))

    assert payload["components"]["critical_nutrient_coverage"] == 2.0
    assert payload["components"]["prenatal_complement_support"] == 0.5
    assert payload["metadata"]["critical_nutrients_missing"] == ["iodine", "vitamin_d", "vitamin_b12"]
    assert payload["metadata"]["prenatal_complement_scores"]["dha"] == 0.5


def test_prenatal_combined_epa_dha_gets_partial_not_full_dha_critical_credit() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(
        name="Complete Prenatal with Omega-3",
        adequacy_results=[_adequacy(n, pct_rda=60) for n in PRENATAL_CORE],
        ingredients=[_ingredient("epa_dha", name="EPA+DHA", quantity=300, unit="mg")],
    ))

    assert payload["metadata"]["prenatal_complement_scores"]["dha"] == 0.5
    assert payload["components"]["critical_nutrient_coverage"] == 5.0
    assert "dha" not in payload["metadata"]["critical_nutrient_scores"]


def test_prenatal_combined_epa_dha_does_not_override_itemized_dha_credit() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(
        name="Complete Prenatal with DHA",
        adequacy_results=[_adequacy(n, pct_rda=60) for n in PRENATAL_CORE],
        ingredients=[
            _ingredient("epa_dha", name="EPA+DHA", quantity=300, unit="mg"),
            _ingredient("dha", name="DHA", quantity=200, unit="mg"),
        ],
    ))

    assert payload["metadata"]["prenatal_complement_scores"]["dha"] == 1.0
    assert payload["components"]["critical_nutrient_coverage"] == 5.0


def test_prenatal_dha_detection_accepts_final_detail_blob_ingredients_alias() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    product = _product(
        name="Prenatal DHA",
        adequacy_results=[_adequacy(n, pct_rda=60) for n in PRENATAL_CORE],
        ingredients=[],
    )
    product["ingredient_quality_data"]["ingredients_scorable"] = [
        _ingredient("dha", name="DHA", quantity=200, unit="mg")
    ]

    payload = score_dose(product)

    assert payload["metadata"]["prenatal_complement_scores"]["dha"] == 1.0
    assert payload["components"]["critical_nutrient_coverage"] == 5.0


def test_prenatal_dha_critical_anchor_accepts_gram_units() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(
        name="Complete Prenatal with DHA",
        adequacy_results=[_adequacy(n, pct_rda=60) for n in PRENATAL_CORE],
        ingredients=[_ingredient("dha", name="DHA", quantity=0.2, unit="g")],
    ))

    assert payload["metadata"]["prenatal_complement_scores"]["dha"] == 1.0
    assert payload["components"]["critical_nutrient_coverage"] == 5.0


def test_prenatal_dha_critical_anchor_accepts_microgram_units() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(
        name="Complete Prenatal with DHA",
        adequacy_results=[_adequacy(n, pct_rda=60) for n in PRENATAL_CORE],
        ingredients=[_ingredient("dha", name="DHA", quantity=200000, unit="mcg")],
    ))

    assert payload["metadata"]["prenatal_complement_scores"]["dha"] == 1.0
    assert payload["components"]["critical_nutrient_coverage"] == 5.0


def test_prenatal_dha_critical_anchor_does_not_use_fish_oil_parent_mass() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(
        name="Complete Prenatal with Fish Oil",
        adequacy_results=[_adequacy(n, pct_rda=60) for n in PRENATAL_CORE],
        ingredients=[_ingredient("fish_oil", name="Fish Oil", quantity=1000, unit="mg")],
    ))

    assert payload["metadata"]["prenatal_complement_scores"]["dha"] == 0.0
    assert payload["components"]["critical_nutrient_coverage"] == 5.0


def test_prenatal_dha_critical_anchor_does_not_match_dhea() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(
        name="Complete Prenatal",
        adequacy_results=[_adequacy(n, pct_rda=60) for n in PRENATAL_CORE],
        ingredients=[_ingredient("dhea", name="DHEA", quantity=200, unit="mg")],
    ))

    assert payload["metadata"]["prenatal_complement_scores"]["dha"] == 0.0
    assert payload["components"]["critical_nutrient_coverage"] == 5.0


def test_prenatal_bundle_context_does_not_trigger_prenatal_critical_anchors() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    product = _product(
        name="Calcium 600",
        adequacy_results=[_adequacy(n) for n in CORE_ANCHORS],
        ingredients=[_ingredient("calcium", name="Calcium", quantity=600, unit="mg")],
    )
    product["brand_name"] = "GNC Women's"
    product["bundleName"] = "Prenatal Program"

    payload = score_dose(product)

    assert payload["metadata"]["critical_nutrient_mode"] == "core_multi"
    assert "dha" not in payload["metadata"]["critical_nutrient_scores"]


def test_no_rda_reference_returns_zero_score_not_none_for_multi_direct_call() -> None:
    from scoring_v4.modules.multi_prenatal_dose import score_dose

    payload = score_dose(_product(adequacy_results=[]))

    assert payload["score"] == 0.0
    assert payload["components"]["rda_ai_coverage"] == 0.0
    assert payload["metadata"]["coverage_status"] == "no_rda_reference_data"


def test_score_multi_prenatal_wires_dose_dimension() -> None:
    from scoring_v4.modules.multi_prenatal import score_multi_prenatal

    breakdown = score_multi_prenatal(_product(
        adequacy_results=[_adequacy(n) for n in CORE_ANCHORS],
        ingredients=[_ingredient("vitamin_c")],
    )).to_breakdown()

    dose = breakdown["dimensions"]["dose"]
    assert dose["score"] is not None
    assert dose["metadata"]["phase"] == "P3.2_multi_prenatal_dose"
    assert breakdown["score_100"] is not None
    assert breakdown["phase"].startswith("P3.")


def test_multi_prenatal_dose_does_not_import_v3_scorer() -> None:
    source = (SCRIPTS_ROOT / "scoring_v4" / "modules" / "multi_prenatal_dose.py").read_text()

    assert "import score_supplements" not in source
    assert "from score_supplements" not in source
