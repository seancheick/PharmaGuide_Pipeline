from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go

# V4 six-pillar maxima — source of truth: scripts/scoring_v4/config/quality_score.json.
# (label, products_core column, max points)  →  formulation/dose/evidence 20,
# transparency/verification 15, safety_hygiene 10  (= 100).
V4_PILLARS = [
    ("Formulation", "pillar_formulation_v4", 20),
    ("Dose", "pillar_dose_v4", 20),
    ("Evidence", "pillar_evidence_v4", 20),
    ("Transparency", "pillar_transparency_v4", 15),
    ("Verification", "pillar_verification_v4", 15),
    ("Safety & Hygiene", "pillar_safety_hygiene_v4", 10),
]


def _render_pillar_bars(pillars, height: int = 320):
    """Render horizontal bars for a list of {label, value, max} dicts.

    Color by % of max: green >=80, yellow 50-79, red <50; grey + "n/a" when
    value is None (product not v4-scored / pillar absent).
    """
    labels = [p["label"] for p in pillars]
    values = [(p["value"] if p["value"] is not None else 0) for p in pillars]
    max_values = [p["max"] for p in pillars]

    colors, text = [], []
    for p in pillars:
        if p["value"] is None:
            colors.append("#94a3b8")  # grey — not scored
            text.append("n/a")
            continue
        pct = (p["value"] / p["max"]) * 100 if p["max"] > 0 else 0
        colors.append("#22c55e" if pct >= 80 else "#eab308" if pct >= 50 else "#ef4444")
        text.append(f"{p['value']:.1f}/{p['max']}")

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=text,
        textposition="auto",
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    fig.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(range=[0, max(max_values) * 1.1], showgrid=False, visible=False),
        yaxis=dict(autorange="reversed"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def score_breakdown_v4(
    formulation: float | None,
    dose: float | None,
    evidence: float | None,
    transparency: float | None,
    verification: float | None,
    safety_hygiene: float | None,
    height: int = 320,
):
    """Render the V4 six-pillar breakdown (maxes 20/20/20/15/15/10)."""
    vals = [formulation, dose, evidence, transparency, verification, safety_hygiene]
    pillars = [
        {"label": lbl, "value": v, "max": mx}
        for (lbl, _col, mx), v in zip(V4_PILLARS, vals)
    ]
    _render_pillar_bars(pillars, height=height)


def score_breakdown(
    ingredient: float,
    safety: float,
    evidence: float,
    brand: float,
    height: int = 300,
):
    """DEPRECATED — V3 four-section breakdown (Ingredient 25 / Safety 30 /
    Evidence 20 / Brand 5). Retained so legacy callers don't break; new code
    should call score_breakdown_v4. The V4 scorer is a six-pillar /100 model."""
    pillars = [
        {"label": "Ingredient Quality", "value": ingredient, "max": 25},
        {"label": "Safety & Purity", "value": safety, "max": 30},
        {"label": "Evidence & Research", "value": evidence, "max": 20},
        {"label": "Brand Trust", "value": brand, "max": 5},
    ]
    _render_pillar_bars(pillars, height=height)
