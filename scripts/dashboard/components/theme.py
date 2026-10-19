"""PharmaGuide dashboard theme: website tokens, validated chart palettes, Plotly template.

Surface/ink/accent tokens mirror ``PharmaGuide Website/src/app/globals.css`` (light only);
change both together. Chart palettes passed the dataviz validator (lightness band,
chroma floor, CVD and normal-vision separation, 3:1 contrast on white) on 2026-10-19.
Streamlit's own theme lives in the repo-root ``.streamlit/config.toml``.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

TOKENS = {
    "background": "#FAF9F6",
    "surface": "#FFFFFF",
    "subtle": "#F2EFE9",
    "ink": "#181A1B",
    "muted": "#63666A",
    "border": "#E5E2DB",
    "border_strong": "#D1CDC4",
    "accent": "#183B3F",
    "accent_soft": "#E6ECEC",
    "link": "#246066",
}
SEVERITY = {  # website severity tokens: text on their *_bg
    "critical": ("#9F2929", "#F5E6E6"),
    "high": ("#AA4E26", "#F7EBE3"),
    "medium": ("#8A611D", "#F6F0E2"),
    "info": ("#77683B", "#F0EDE2"),
    "ok": ("#3F6250", "#E9EEEA"),
}
# Categorical, fixed order = PILLARS order. Validated.
PILLAR_COLORS = {
    "formulation": "#009C9E",
    "dose": "#E06A2C",
    "evidence": "#3D6FD1",
    "transparency": "#B88200",
    "verification": "#C8578B",
    "safety_hygiene": "#3C8A3C",
}
# Receipt entry kinds. Validated as a 5-slot set; greys are labelled non-identity tracks.
KIND_COLORS = {
    "earned": "#009C9E",
    "neutral": "#B88200",
    "disclosure": "#3D6FD1",
    "deduction": "#C0392B",
    "cap": "#7B5CC4",
    "floor": "#7B5CC4",
    "rounding": "#B5AFA3",
    "not_earned": "#E5E2DB",
}
KIND_LABELS = {
    "earned": "Earned",
    "neutral": "Baseline credit",
    "disclosure": "Disclosure credit",
    "deduction": "Deducted",
    "cap": "Capped",
    "floor": "Raised to minimum",
    "rounding": "Rounding",
    "not_earned": "Not earned",
}

pio.templates["pg_dashboard"] = go.layout.Template(
    layout=go.Layout(
        font={"family": "Geist, system-ui, sans-serif", "color": TOKENS["ink"], "size": 13},
        paper_bgcolor=TOKENS["surface"],
        plot_bgcolor=TOKENS["surface"],
        colorway=list(PILLAR_COLORS.values()),
        margin={"l": 8, "r": 8, "t": 36, "b": 8},
        xaxis={"gridcolor": TOKENS["border"], "zerolinecolor": TOKENS["border_strong"], "linecolor": TOKENS["border"],
               "tickfont": {"color": TOKENS["muted"]}, "title": {"font": {"color": TOKENS["muted"]}}},
        yaxis={"gridcolor": TOKENS["border"], "zerolinecolor": TOKENS["border_strong"], "linecolor": TOKENS["border"],
               "tickfont": {"color": TOKENS["muted"]}, "title": {"font": {"color": TOKENS["muted"]}}},
        hoverlabel={"bgcolor": TOKENS["surface"], "bordercolor": TOKENS["border_strong"],
                    "font": {"family": "Geist, system-ui, sans-serif", "color": TOKENS["ink"]}},
        legend={"orientation": "h", "yanchor": "top", "y": -0.18, "x": 0, "font": {"color": TOKENS["muted"]}},
        bargap=0.25,
        title={"font": {"family": "Newsreader, Georgia, serif", "size": 17, "color": TOKENS["ink"]}, "x": 0},
    )
)
pio.templates.default = "pg_dashboard"

_CSS = f"""
<style>
.block-container {{ padding-top: 1.6rem; max-width: 1480px; }}
h1, h2, h3 {{ letter-spacing: -0.012em; }}
[data-testid="stMetricValue"] {{ font-weight: 500; }}
[data-testid="stMetricValue"] p {{ white-space: normal !important; overflow: visible !important; text-overflow: clip !important; line-height: 1.15; }}
[data-testid="stMetricLabel"] p {{ color: {TOKENS["muted"]}; font-size: 0.8rem; text-transform: uppercase;
    letter-spacing: 0.06em; }}
.pg-eyebrow {{ color: {TOKENS["muted"]}; font-size: 0.75rem; letter-spacing: 0.12em; text-transform: uppercase;
    margin-bottom: 0.1rem; }}
.pg-sub {{ color: {TOKENS["muted"]}; margin-top: -0.4rem; margin-bottom: 0.9rem; }}
.pg-chip {{ display: inline-block; padding: 0.12rem 0.55rem; border-radius: 999px; font-size: 0.78rem;
    border: 1px solid {TOKENS["border"]}; background: {TOKENS["surface"]}; color: {TOKENS["ink"]};
    margin: 0 0.3rem 0.3rem 0; white-space: nowrap; }}
.pg-chip.accent {{ background: {TOKENS["accent_soft"]}; border-color: transparent; color: {TOKENS["accent"]}; }}
{"".join(f".pg-chip.{name} {{ background: {bg}; border-color: transparent; color: {fg}; }}" for name, (fg, bg) in SEVERITY.items())}
.pg-banner {{ border: 1px solid {TOKENS["border"]}; background: {TOKENS["surface"]}; border-radius: 8px;
    padding: 0.55rem 0.8rem; margin-bottom: 1rem; font-size: 0.85rem; color: {TOKENS["muted"]}; }}
.pg-banner b {{ color: {TOKENS["ink"]}; font-weight: 500; }}
.pg-pillar {{ display: grid; grid-template-columns: 9.5rem 1fr 4.2rem; align-items: center; gap: 0.6rem;
    margin: 0.28rem 0; font-size: 0.9rem; }}
.pg-track {{ height: 0.62rem; background: {TOKENS["border"]}; border-radius: 4px; overflow: hidden; }}
.pg-fill {{ height: 100%; border-radius: 4px; }}
.pg-state {{ color: {TOKENS["muted"]}; font-size: 0.78rem; grid-column: 2 / 4; margin-top: -0.2rem; }}
.pg-sum {{ font-size: 0.85rem; color: {TOKENS["muted"]}; margin: 0.4rem 0 0.2rem; }}
.pg-sum b {{ color: {TOKENS["ink"]}; font-weight: 500; }}
.pg-card {{ border: 1px solid {TOKENS["border"]}; background: {TOKENS["surface"]}; border-radius: 8px; padding: 0.9rem 1rem; }}
.pg-why {{ background: {TOKENS["subtle"]}; border-radius: 6px; padding: 0.55rem 0.75rem; font-size: 0.88rem; margin-bottom: 0.7rem; }}
.pg-line {{ display: grid; grid-template-columns: 4.6rem 1fr auto; gap: 0.7rem; align-items: baseline;
    padding: 0.42rem 0; border-bottom: 1px solid {TOKENS["border"]}; font-size: 0.9rem; }}
.pg-line > span, .pg-total > span {{ min-width: 0; }}
.pg-pts {{ font-family: "Geist Mono", ui-monospace, monospace; text-align: right; font-weight: 500; }}
.pg-id {{ display: block; font-family: "Geist Mono", ui-monospace, monospace; font-size: 0.72rem; color: {TOKENS["muted"]};
    overflow-wrap: anywhere; }}
.pg-detail {{ display: block; font-size: 0.8rem; color: {TOKENS["muted"]}; }}
.pg-total {{ display: grid; grid-template-columns: 4.6rem 1fr auto; gap: 0.7rem; padding: 0.55rem 0 0.1rem;
    font-weight: 500; font-size: 0.95rem; }}
.pg-label {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
.pg-label-wrap {{ overflow-x: auto; }}
.pg-label th {{ white-space: nowrap; text-align: left; font-weight: 500; color: {TOKENS["muted"]}; font-size: 0.75rem; text-transform: uppercase;
    letter-spacing: 0.04em; border-bottom: 2px solid {TOKENS["ink"]}; padding: 0.3rem 0.3rem; font-size: 0.68rem; }}
.pg-label td {{ border-bottom: 1px solid {TOKENS["border"]}; padding: 0.3rem 0.3rem; vertical-align: top; }}
.pg-label th.r {{ text-align: right; }}
.pg-card-head {{ display: flex; align-items: center; gap: 0.5rem; font-weight: 500; font-size: 1rem; margin-bottom: 0.5rem; }}
.pg-card-score {{ margin-left: auto; font-family: "Geist Mono", ui-monospace, monospace; }}
.pg-dot {{ width: 0.62rem; height: 0.62rem; border-radius: 3px; display: inline-block; }}
.pg-label td.num {{ text-align: right; font-family: "Geist Mono", ui-monospace, monospace; }}
.pg-label td.over {{ color: {SEVERITY["critical"][0]}; font-weight: 600; }}
.pg-label .form {{ display: block; color: {TOKENS["muted"]}; font-size: 0.76rem; }}
.pg-facts-head {{ font-family: Newsreader, Georgia, serif; font-size: 1.35rem; font-weight: 600; margin-bottom: 0.2rem; }}
@media (max-width: 1280px) {{
  [data-testid="stHorizontalBlock"]:has(.pg-card-head) {{ flex-wrap: wrap; }}
  [data-testid="stHorizontalBlock"]:has(.pg-card-head) > [data-testid="stColumn"] {{ min-width: 100%; }}
}}
.pg-facts-meta {{ font-size: 0.84rem; color: {TOKENS["muted"]}; margin-bottom: 0.5rem; }}
</style>
"""


def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
