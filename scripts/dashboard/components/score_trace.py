import pandas as pd
import streamlit as st

def _append_running_row(rows, step, delta, running_total, note=""):
    running_total += float(delta or 0)
    rows.append(
        {
            "step": step,
            "delta": round(float(delta or 0), 2),
            "running_total": round(running_total, 2),
            "note": note,
        }
    )
    return running_total


def _section_a_rows(section_breakdown: dict):
    sub = section_breakdown.get("ingredient_quality", {}).get("sub", {})
    rows = []
    running = 0.0
    component_labels = [
        ("A1", "Bioavailability"),
        ("A2", "Premium forms"),
        ("A3", "Delivery"),
        ("A4", "Absorption"),
        ("A5a", "Organic certification"),
        ("A5b", "Standardized botanical"),
        ("A5c", "Synergy cluster"),
        ("A5d", "Non-GMO verified"),
    ]
    for key, label in component_labels:
        running = _append_running_row(rows, f"{key} {label}", sub.get(key, 0.0), running)
    formulation_subtotal = sum(float(sub.get(key, 0.0) or 0.0) for key in ["A5a", "A5b", "A5c", "A5d"])
    formulation_adjust = float(sub.get("A5", 0.0) or 0.0) - formulation_subtotal
    if formulation_adjust:
        running = _append_running_row(rows, "A5 formulation cap adjustment", formulation_adjust, running)
    running = _append_running_row(rows, "A6 single efficiency", sub.get("A6", 0.0), running)
    running = _append_running_row(rows, "Probiotic category bonus", sub.get("probiotic_bonus", 0.0), running)
    running = _append_running_row(rows, "Omega-3 dose bonus", sub.get("omega3_dose_bonus", 0.0), running)
    pool_adjust = float(sub.get("category_bonus_total", 0.0) or 0.0) - (
        float(sub.get("probiotic_bonus", 0.0) or 0.0) + float(sub.get("omega3_dose_bonus", 0.0) or 0.0)
    )
    if pool_adjust:
        running = _append_running_row(rows, "Category bonus pool adjustment", pool_adjust, running)
    return rows


def _section_b_rows(section_breakdown: dict):
    data = section_breakdown.get("safety_purity", {})
    sub = data.get("sub", {})
    bonuses = float(sub.get("bonuses", 0.0) or 0.0)
    penalties = float(sub.get("penalties", 0.0) or 0.0)
    raw = float(sub.get("raw", data.get("score", 0.0)) or 0.0)
    base_score = raw - bonuses + penalties
    rows = []
    running = 0.0
    running = _append_running_row(rows, "Base safety score", base_score, running)
    for key, label in [
        ("B3", "Claim compliance"),
        ("B4a", "Third-party programs"),
        ("B4b", "GMP"),
        ("B4c", "Batch traceability"),
        ("B_hypoallergenic", "Hypoallergenic"),
    ]:
        running = _append_running_row(rows, label, sub.get(key, 0.0), running)
    bonus_adjust = bonuses - sum(float(sub.get(key, 0.0) or 0.0) for key in ["B3", "B4a", "B4b", "B4c", "B_hypoallergenic"])
    if bonus_adjust:
        running = _append_running_row(rows, "Bonus pool adjustment", bonus_adjust, running)
    for key, label in [
        ("B0_moderate_penalty", "Moderate risk penalty"),
        ("B1_penalty", "Harmful additives penalty"),
        ("B2_penalty", "Allergen penalty"),
        ("B5_penalty", "Proprietary blend penalty"),
        ("B6_penalty", "Disease claims penalty"),
        ("B7_penalty", "Dose safety penalty"),
    ]:
        value = -float(sub.get(key, 0.0) or 0.0)
        running = _append_running_row(rows, label, value, running)
    clamp_adjust = float(data.get("score", 0.0) or 0.0) - raw
    if clamp_adjust:
        running = _append_running_row(rows, "Section clamp adjustment", clamp_adjust, running)
    return rows


def _section_c_rows(section_breakdown: dict):
    data = section_breakdown.get("evidence_research", {})
    ingredient_points = data.get("ingredient_points") or {}
    rows = []
    running = 0.0
    if ingredient_points:
        for ingredient, points in sorted(ingredient_points.items(), key=lambda x: x[1], reverse=True):
            running = _append_running_row(rows, f"Evidence: {ingredient}", points, running)
        cap_adjust = float(data.get("score", 0.0) or 0.0) - sum(float(v or 0.0) for v in ingredient_points.values())
        if cap_adjust:
            running = _append_running_row(rows, "Evidence cap / weighting adjustment", cap_adjust, running)
    else:
        running = _append_running_row(rows, "Evidence section total", data.get("score", 0.0), running)
    return rows


def _section_d_rows(section_breakdown: dict):
    sub = section_breakdown.get("brand_trust", {}).get("sub", {})
    rows = []
    running = 0.0
    for key, label in [
        ("D1", "Trusted manufacturer"),
        ("D2", "Full disclosure"),
        ("D3", "Physician formulated"),
        ("D4", "High-standard region"),
        ("D5", "Sustainable packaging"),
    ]:
        running = _append_running_row(rows, label, sub.get(key, 0.0), running)
    return rows


def build_score_trace_model(section_breakdown: dict) -> dict:
    section_models = [
        {
            "section": "Ingredient Quality",
            "score": float(section_breakdown.get("ingredient_quality", {}).get("score", 0.0) or 0.0),
            "max": float(section_breakdown.get("ingredient_quality", {}).get("max", 0.0) or 0.0),
            "rows": _section_a_rows(section_breakdown),
        },
        {
            "section": "Safety & Purity",
            "score": float(section_breakdown.get("safety_purity", {}).get("score", 0.0) or 0.0),
            "max": float(section_breakdown.get("safety_purity", {}).get("max", 0.0) or 0.0),
            "rows": _section_b_rows(section_breakdown),
        },
        {
            "section": "Evidence & Research",
            "score": float(section_breakdown.get("evidence_research", {}).get("score", 0.0) or 0.0),
            "max": float(section_breakdown.get("evidence_research", {}).get("max", 0.0) or 0.0),
            "rows": _section_c_rows(section_breakdown),
        },
        {
            "section": "Brand Trust",
            "score": float(section_breakdown.get("brand_trust", {}).get("score", 0.0) or 0.0),
            "max": float(section_breakdown.get("brand_trust", {}).get("max", 0.0) or 0.0),
            "rows": _section_d_rows(section_breakdown),
        },
    ]

    overall_rows = []
    running = 0.0
    for section in section_models:
        running = _append_running_row(overall_rows, section["section"], section["score"], running)
    violation_penalty = float(section_breakdown.get("violation_penalty", 0.0) or 0.0)
    if violation_penalty:
        running = _append_running_row(overall_rows, "Manufacturer violation penalty", violation_penalty, running)

    return {
        "section_rows": [
            {"section": section["section"], "score": section["score"], "max": section["max"]}
            for section in section_models
        ],
        "section_models": section_models,
        "overall_rows": overall_rows,
        "base_total": round(sum(section["score"] for section in section_models), 2),
        "violation_penalty": round(violation_penalty, 2),
        "final_score": round(running, 2),
    }


def score_trace(section_breakdown: dict, bonuses: list[dict], penalties: list[dict]):
    """
    Trace view showing exact section math, component-level accumulation, and final running score.
    """
    st.subheader("🔍 Score Trace")
    model = build_score_trace_model(section_breakdown)

    st.write("#### Detailed Component Breakdown")
    for section in model["section_models"]:
        st.write(f"**{section['section']}** (Score: {section['score']:.1f}/{section['max']:.1f})")
        st.dataframe(pd.DataFrame(section["rows"]), width="stretch", hide_index=True, height=280)

    probiotic_breakdown = (
        section_breakdown.get("ingredient_quality", {})
        .get("sub", {})
        .get("probiotic_breakdown", {})
    )
    if probiotic_breakdown.get("eligibility"):
        st.write("#### Probiotic Gate")
        eligibility = probiotic_breakdown["eligibility"]
        checks = eligibility.get("strict_gate_checks", {})
        inputs = eligibility.get("strict_gate_inputs", {})
        if checks:
            st.dataframe(
                pd.DataFrame([{"check": key, "passed": value} for key, value in checks.items()]),
                width="stretch",
                hide_index=True,
                height=220,
            )
        if inputs:
            st.dataframe(
                pd.DataFrame([{"field": key, "value": str(value)} for key, value in inputs.items()]),
                width="stretch",
                hide_index=True,
                height=220,
            )

    st.write("#### Section Totals")
    st.dataframe(pd.DataFrame(model["section_rows"]), width="stretch", height=220, hide_index=True)

    st.write("#### Running Score Trace")
    st.dataframe(pd.DataFrame(model["overall_rows"]), width="stretch", height=320, hide_index=True)

    st.write("#### Final Score Math")
    st.markdown(
        f"**Section totals: {model['base_total']:.1f}** + "
        f"**Violation penalty: {model['violation_penalty']:+.1f}** = "
        f"**{model['final_score']:.1f}**"
    )
