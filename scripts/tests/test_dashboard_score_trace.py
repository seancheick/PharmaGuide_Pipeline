from scripts.dashboard.components.score_trace import build_score_trace_model


def test_score_trace_model_uses_real_section_math_without_double_counting():
    section_breakdown = {
        "ingredient_quality": {
            "score": 5.0,
            "max": 25.0,
            "sub": {
                "A1": 1.0,
                "A2": 0.0,
                "A3": 1.0,
                "A4": 0.0,
                "A5": 1.0,
                "A5a": 0.0,
                "A5b": 1.0,
                "A5c": 0.0,
                "A5d": 0.0,
                "A6": 0.0,
                "probiotic_bonus": 2.0,
                "omega3_dose_bonus": 0.0,
                "category_bonus_total": 2.0,
                "core_quality": 3.0,
                "category_bonus_pool_cap": 5.0,
            },
        },
        "safety_purity": {
            "score": 29.5,
            "max": 30.0,
            "sub": {
                "B0_moderate_penalty": 0.0,
                "B1_penalty": 0.5,
                "B2_penalty": 0.0,
                "B3": 2.0,
                "B4a": 3.0,
                "B4b": 0.0,
                "B4c": 0.0,
                "B_hypoallergenic": 0.0,
                "B5_penalty": 0.0,
                "B6_penalty": 0.0,
                "B7_penalty": 0.0,
                "bonuses": 5.0,
                "penalties": 0.5,
                "raw": 29.5,
            },
        },
        "evidence_research": {
            "score": 4.0,
            "max": 20.0,
            "matched_entries": 1,
            "ingredient_points": {"ingredient a": 4.0},
        },
        "brand_trust": {
            "score": 3.0,
            "max": 5.0,
            "sub": {"D1": 2.0, "D2": 1.0, "D3": 0.0, "D4": 0.0, "D5": 0.0},
        },
        "violation_penalty": -1.0,
    }

    model = build_score_trace_model(section_breakdown)

    assert model["final_score"] == 40.5
    assert model["base_total"] == 41.5
    assert any(row["step"] == "Manufacturer violation penalty" for row in model["overall_rows"])
    assert model["section_rows"][0]["section"] == "Ingredient Quality"

