"""
CAERS Adverse Events Audit Dashboard

Deep-dive into FDA CAERS pharmacovigilance data: ingredient-level signals,
outcome breakdowns, cross-reference with banned/recalled and IQM data,
and B8 scoring impact analysis.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.dashboard.components.data_table import data_table
from scripts.dashboard.components.metric_cards import metric_row


def render_audit_caers(data):
    """Main rendering function for CAERS audit dashboard."""
    signals = data.caers_signals
    metadata = data.caers_metadata

    if not signals:
        st.warning(
            "No CAERS data loaded. Run `python3 scripts/api_audit/ingest_caers.py` "
            "to download and process FDA CAERS bulk data."
        )
        return

    _render_overview(signals, metadata)
    st.divider()

    tab_signals, tab_cross, tab_impact, tab_reactions, tab_raw = st.tabs([
        "Signal Explorer",
        "Cross-Reference Audit",
        "B8 Scoring Impact",
        "Reaction Analysis",
        "Raw Data",
    ])
    with tab_signals:
        _render_signal_explorer(signals)
    with tab_cross:
        _render_cross_reference(signals, data)
    with tab_impact:
        _render_scoring_impact(signals, data)
    with tab_reactions:
        _render_reaction_analysis(signals)
    with tab_raw:
        _render_raw_data(signals, metadata)


def _render_overview(signals, metadata):
    st.write("### FDA CAERS Pharmacovigilance Overview")
    st.caption(
        "Real-world adverse event reports from consumers and healthcare providers. "
        "Source: FDA Center for Food Safety and Applied Nutrition (CFSAN)."
    )

    total = len(signals)
    strong = [s for s in signals.values() if s.get("signal_strength") == "strong"]
    moderate = [s for s in signals.values() if s.get("signal_strength") == "moderate"]
    weak = [s for s in signals.values() if s.get("signal_strength") == "weak"]

    total_serious = sum(s.get("serious_reports", 0) for s in signals.values())
    total_deaths = sum(s.get("outcomes", {}).get("death", 0) for s in signals.values())
    total_hosp = sum(s.get("outcomes", {}).get("hospitalization", 0) for s in signals.values())
    reports_analyzed = metadata.get("total_supplement_reports_analyzed", 0)

    metric_row([
        ("Ingredients Tracked", total),
        ("Strong Signals", len(strong)),
        ("Moderate Signals", len(moderate)),
        ("Weak Signals", len(weak)),
    ])
    metric_row([
        ("Reports Analyzed", f"{reports_analyzed:,}"),
        ("Total Serious Events", f"{total_serious:,}"),
        ("Total Deaths Reported", f"{total_deaths:,}"),
        ("Total Hospitalizations", f"{total_hosp:,}"),
    ])


def _render_signal_explorer(signals):
    st.write("### Signal Explorer")
    st.caption("Filter and explore individual ingredient adverse event signals.")

    col1, col2, col3 = st.columns(3)
    with col1:
        strength_filter = st.multiselect(
            "Signal strength", ["strong", "moderate", "weak"],
            default=["strong", "moderate"],
            key="caers_explore_strength",
        )
    with col2:
        min_serious = st.number_input("Min serious reports", 0, 10000, 10, key="caers_min_serious")
    with col3:
        search = st.text_input("Search ingredient", "", key="caers_search")

    rows = []
    for cid, sig in signals.items():
        if strength_filter and sig.get("signal_strength") not in strength_filter:
            continue
        if sig.get("serious_reports", 0) < min_serious:
            continue
        if search and search.lower() not in cid.lower():
            continue
        outcomes = sig.get("outcomes", {})
        rows.append({
            "Ingredient": cid.replace("_", " ").title(),
            "canonical_id": cid,
            "Signal": sig.get("signal_strength", ""),
            "Serious": sig.get("serious_reports", 0),
            "Total": sig.get("total_reports", 0),
            "Deaths": outcomes.get("death", 0),
            "Hospitalized": outcomes.get("hospitalization", 0),
            "ER": outcomes.get("er_visit", 0),
            "Life Threat": outcomes.get("life_threatening", 0),
            "Disabled": outcomes.get("disability", 0),
            "Years": sig.get("year_range", ""),
            "B8 Penalty": _b8_penalty(sig.get("signal_strength", "")),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No signals match the current filters.")
        return

    df = df.sort_values("Serious", ascending=False)
    st.metric("Matching ingredients", len(df))

    display_cols = [
        "Ingredient", "Signal", "Serious", "Total", "Deaths",
        "Hospitalized", "ER", "Life Threat", "Years", "B8 Penalty",
    ]
    st.dataframe(df[display_cols], use_container_width=True, height=500)

    csv = df[display_cols].to_csv(index=False)
    st.download_button("Download CSV", csv, "caers_explorer.csv", "text/csv", key="caers_explore_csv")

    # Detail expander for selected ingredient
    st.write("#### Ingredient Detail")
    selected = st.selectbox(
        "Select ingredient for detail",
        [r["Ingredient"] for r in rows[:50]],
        key="caers_detail_select",
    )
    if selected:
        cid = selected.lower().replace(" ", "_")
        sig = signals.get(cid, {})
        if sig:
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**{selected}** — `{cid}`")
                st.write(f"Signal: **{sig.get('signal_strength', '')}**")
                st.write(f"Reports: {sig.get('total_reports', 0)} total, {sig.get('serious_reports', 0)} serious")
                st.write(f"Year range: {sig.get('year_range', '')}")
            with col2:
                st.write("**Top Reactions:**")
                for r in sig.get("top_reactions", []):
                    st.write(f"- {r}")


def _render_cross_reference(signals, data):
    """Cross-reference CAERS signals with banned_recalled and IQM data."""
    st.write("### Cross-Reference Audit")
    st.caption(
        "Identify gaps: ingredients with CAERS signals that are NOT in banned_recalled, "
        "and banned_recalled entries that have NO CAERS signal."
    )

    # Load banned_recalled
    banned_path = Path("scripts/data/banned_recalled_ingredients.json")
    banned_data = {}
    try:
        with open(banned_path) as f:
            raw = json.load(f)
        for entry in raw.get("ingredients", []):
            std = entry.get("standard_name", "").lower().replace(" ", "_")
            banned_data[std] = entry
            for alias in entry.get("aliases", []):
                banned_data[alias.lower().replace(" ", "_")] = entry
    except (FileNotFoundError, json.JSONDecodeError):
        st.warning("Could not load banned_recalled_ingredients.json")

    # Cross-reference
    caers_not_banned = []
    caers_and_banned = []
    for cid, sig in sorted(signals.items(), key=lambda x: -x[1].get("serious_reports", 0)):
        in_banned = cid in banned_data or cid.replace("_", " ") in banned_data
        entry = {
            "Ingredient": cid.replace("_", " ").title(),
            "canonical_id": cid,
            "Signal": sig.get("signal_strength", ""),
            "Serious": sig.get("serious_reports", 0),
            "Deaths": sig.get("outcomes", {}).get("death", 0),
            "In Banned/Recalled": "Yes" if in_banned else "No",
        }
        if in_banned:
            matched = banned_data.get(cid) or banned_data.get(cid.replace("_", " "), {})
            entry["Banned Status"] = matched.get("status", "unknown")
            caers_and_banned.append(entry)
        else:
            caers_not_banned.append(entry)

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"#### CAERS signals NOT in banned/recalled ({len(caers_not_banned)})")
        st.caption("These ingredients have real-world adverse events but no regulatory action. Review candidates.")
        if caers_not_banned:
            not_banned_df = pd.DataFrame(caers_not_banned)
            strong_not_banned = not_banned_df[not_banned_df["Signal"] == "strong"]
            if not strong_not_banned.empty:
                st.error(f"**{len(strong_not_banned)} strong signals** not in banned/recalled!")
            st.dataframe(not_banned_df, use_container_width=True, height=350)
            csv = not_banned_df.to_csv(index=False)
            st.download_button("Download", csv, "caers_not_banned.csv", "text/csv", key="caers_not_banned_csv")

    with col2:
        st.write(f"#### CAERS signals WITH banned/recalled match ({len(caers_and_banned)})")
        st.caption("Regulatory action corroborated by real-world adverse events.")
        if caers_and_banned:
            both_df = pd.DataFrame(caers_and_banned)
            st.dataframe(both_df, use_container_width=True, height=350)


def _render_scoring_impact(signals, data):
    """Show how B8 CAERS penalties affect product scores."""
    st.write("### B8 Scoring Impact Analysis")

    # Load scoring config
    scoring_config = data.scoring_config or {}
    b8_cfg = scoring_config.get("section_B_safety_purity", {}).get("B8_caers_adverse_events", {})

    col1, col2 = st.columns(2)
    with col1:
        st.write("#### Current B8 Config")
        st.json(b8_cfg)
    with col2:
        st.write("#### Penalty Schedule")
        schedule = pd.DataFrame([
            {"Signal": "Strong (100+ serious)", "Penalty": b8_cfg.get("strong_penalty", 4.0), "Example": "kratom, green tea extract"},
            {"Signal": "Moderate (25-99)", "Penalty": b8_cfg.get("moderate_penalty", 2.0), "Example": "turmeric, ashwagandha"},
            {"Signal": "Weak (10-24)", "Penalty": b8_cfg.get("weak_penalty", 1.0), "Example": "elderberry, boswellia"},
        ])
        data_table(schedule)
        st.write(f"**Cap:** {b8_cfg.get('cap', 5.0)} pts per product")
        st.write(f"**Enabled:** {'Yes' if b8_cfg.get('enabled') else 'No'}")

    st.divider()

    # Impact simulation — how many ingredients at each penalty level
    st.write("#### Impact Distribution")
    penalty_data = []
    for cid, sig in signals.items():
        strength = sig.get("signal_strength", "")
        pen = _b8_penalty(strength)
        if pen > 0:
            penalty_data.append({
                "Ingredient": cid.replace("_", " ").title(),
                "Signal": strength,
                "Penalty": pen,
                "Serious Reports": sig.get("serious_reports", 0),
            })

    if penalty_data:
        pen_df = pd.DataFrame(penalty_data)
        fig = px.histogram(
            pen_df, x="Penalty", color="Signal",
            color_discrete_map={"strong": "#dc2626", "moderate": "#f59e0b", "weak": "#6b7280"},
            title="Ingredients by B8 Penalty Level",
            nbins=10,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Total penalty impact summary
        total_strong = pen_df[pen_df["Signal"] == "strong"].shape[0]
        total_moderate = pen_df[pen_df["Signal"] == "moderate"].shape[0]
        total_weak = pen_df[pen_df["Signal"] == "weak"].shape[0]
        st.write(
            f"**Products containing strong-signal ingredients will lose up to "
            f"{b8_cfg.get('strong_penalty', 4.0)} pts** (capped at {b8_cfg.get('cap', 5.0)})."
        )
        st.write(
            f"Distribution: {total_strong} ingredients at -{b8_cfg.get('strong_penalty', 4.0)}, "
            f"{total_moderate} at -{b8_cfg.get('moderate_penalty', 2.0)}, "
            f"{total_weak} at -{b8_cfg.get('weak_penalty', 1.0)}"
        )


def _render_reaction_analysis(signals):
    """Aggregate reaction analysis across all signals."""
    st.write("### Reaction Analysis")
    st.caption("Most common adverse reactions reported across all supplement ingredients.")

    reaction_counts = defaultdict(int)
    for sig in signals.values():
        for reaction in sig.get("top_reactions", []):
            reaction_counts[reaction.title()] += 1

    if not reaction_counts:
        st.info("No reaction data available.")
        return

    top_reactions = sorted(reaction_counts.items(), key=lambda x: -x[1])[:30]
    react_df = pd.DataFrame([{"Reaction": r, "Ingredients Affected": c} for r, c in top_reactions])

    fig = px.bar(
        react_df, x="Reaction", y="Ingredients Affected",
        title="Top 30 Adverse Reactions (by ingredient count)",
        color="Ingredients Affected",
        color_continuous_scale="Reds",
    )
    fig.update_layout(xaxis_tickangle=-45, height=450)
    st.plotly_chart(fig, use_container_width=True)

    # Death-associated ingredients
    st.divider()
    st.write("#### Ingredients with Reported Deaths")
    death_rows = []
    for cid, sig in signals.items():
        deaths = sig.get("outcomes", {}).get("death", 0)
        if deaths > 0:
            death_rows.append({
                "Ingredient": cid.replace("_", " ").title(),
                "Deaths": deaths,
                "Total Serious": sig.get("serious_reports", 0),
                "Signal": sig.get("signal_strength", ""),
                "Top Reactions": ", ".join(sig.get("top_reactions", [])[:3]),
            })
    if death_rows:
        death_df = pd.DataFrame(sorted(death_rows, key=lambda x: -x["Deaths"]))
        st.metric("Ingredients with death reports", len(death_df))
        st.dataframe(death_df, use_container_width=True, height=350)
    else:
        st.info("No death-associated signals found.")


def _render_raw_data(signals, metadata):
    """Raw JSON data view for auditing."""
    st.write("### Raw Data")

    with st.expander("Metadata"):
        st.json(metadata)

    st.write(f"**Total signals:** {len(signals)}")
    search = st.text_input("Search ingredient", "", key="caers_raw_search")
    for cid in sorted(signals.keys()):
        if search and search.lower() not in cid:
            continue
        with st.expander(f"{cid} — {signals[cid].get('signal_strength', '')} ({signals[cid].get('serious_reports', 0)} serious)"):
            st.json(signals[cid])


def _b8_penalty(signal_strength: str) -> float:
    """Map signal strength to default B8 penalty."""
    return {"strong": 4.0, "moderate": 2.0, "weak": 1.0}.get(signal_strength, 0.0)
