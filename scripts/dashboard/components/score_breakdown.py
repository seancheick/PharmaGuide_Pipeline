import streamlit as st
import plotly.graph_objects as go

def score_breakdown(
    ingredient: float, 
    safety: float, 
    evidence: float, 
    brand: float,
    height: int = 300
):
    """
    Renders 4 horizontal Plotly bars for the scoring pillars.
    Colors based on % of max: Green >= 80%, Yellow 50-79%, Red < 50%.
    """
    pillars = [
        {"label": "Ingredient Quality", "value": ingredient, "max": 25},
        {"label": "Safety & Purity", "value": safety, "max": 30},
        {"label": "Evidence & Research", "value": evidence, "max": 20},
        {"label": "Brand Trust", "value": brand, "max": 5},
    ]
    
    labels = [p["label"] for p in pillars]
    values = [p["value"] for p in pillars]
    max_values = [p["max"] for p in pillars]
    
    colors = []
    for p in pillars:
        pct = (p["value"] / p["max"]) * 100 if p["max"] > 0 else 0
        if pct >= 80:
            colors.append("#22c55e") # Green
        elif pct >= 50:
            colors.append("#eab308") # Yellow
        else:
            colors.append("#ef4444") # Red

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation='h',
        marker_color=colors,
        text=[f"{v}/{m}" for v, m in zip(values, max_values)],
        textposition='auto',
        hovertemplate="%{y}: %{x}/%{customdata}<extra></extra>",
        customdata=max_values
    ))
    
    fig.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(range=[0, max(max_values) * 1.1], showgrid=False, visible=False),
        yaxis=dict(autorange="reversed"),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
    )
    
    st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
