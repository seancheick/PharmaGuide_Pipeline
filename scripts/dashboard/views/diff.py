from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from scripts.dashboard.components import _safe_columns, _safe_tabs
from scripts.dashboard.components.data_table import data_table

# V4 pillar columns for per-pillar release deltas (label, column).
_PILLAR_DIFF = [
    ("Formulation", "pillar_formulation_v4"),
    ("Dose", "pillar_dose_v4"),
    ("Evidence", "pillar_evidence_v4"),
    ("Transparency", "pillar_transparency_v4"),
    ("Verification", "pillar_verification_v4"),
    ("Safety & Hygiene", "pillar_safety_hygiene_v4"),
]


def _release_diff_query(conn: sqlite3.Connection) -> str:
    """SELECT base columns + V4 pillars, NULL-filling pillar columns that an
    older release snapshot predates (so the diff never errors)."""
    have = {row[1] for row in conn.execute("PRAGMA table_info(products_core)")}
    extra = []
    for col in ["quality_score_v4_100"] + [c for _l, c in _PILLAR_DIFF]:
        extra.append(col if col in have else f"NULL AS {col}")
    return (
        "SELECT dsld_id, product_name, brand_name, score_100_equivalent AS score, "
        "verdict, " + ", ".join(extra) + " FROM products_core"
    )


def render_diff(data):
    history = data.build_history
    if not history:
        st.info("No release builds discovered.")
        return

    labels = [entry["label"] for entry in history]
    label_to_entry = {entry["label"]: entry for entry in history}
    col1, col2, col3 = _safe_columns([1, 1, 1])
    with col1:
        base_label = st.selectbox("Release A", labels, index=min(1, len(labels) - 1))
    with col2:
        candidate_label = st.selectbox("Release B", labels, index=0)
    with col3:
        delta_only = st.toggle("Only delta > 3 pts", value=True)

    if base_label == candidate_label:
        st.info("Select two different releases to compare.")
        return

    render_release_comparison(label_to_entry[base_label]["db_path"], label_to_entry[candidate_label]["db_path"], delta_only)


def render_release_comparison(path_a: Path | None, path_b: Path | None, delta_only: bool):
    if not path_a or not path_b:
        st.warning("One of the selected builds is missing its SQLite database.")
        return

    conn_a = sqlite3.connect(f"file:{path_a}?mode=ro", uri=True)
    conn_b = sqlite3.connect(f"file:{path_b}?mode=ro", uri=True)
    try:
        df_a = pd.read_sql_query(_release_diff_query(conn_a), conn_a)
        df_b = pd.read_sql_query(_release_diff_query(conn_b), conn_b)
    finally:
        conn_a.close()
        conn_b.close()

    merged = pd.merge(df_a, df_b, on="dsld_id", how="outer", suffixes=("_A", "_B"), indicator=True)
    merged["score_A"] = merged["score_A"].fillna(0.0)
    merged["score_B"] = merged["score_B"].fillna(0.0)
    merged["delta"] = merged["score_B"] - merged["score_A"]

    summary = pd.DataFrame(
        [
            {"metric": "Products in A", "value": len(df_a)},
            {"metric": "Products in B", "value": len(df_b)},
            {"metric": "Added", "value": int((merged["_merge"] == "right_only").sum())},
            {"metric": "Removed", "value": int((merged["_merge"] == "left_only").sum())},
            {"metric": "Score changes", "value": int((merged["delta"].abs() > 0.01).sum())},
            {"metric": "Verdict changes", "value": int((merged["verdict_A"] != merged["verdict_B"]).sum())},
        ]
    )
    st.dataframe(summary, width="stretch", hide_index=True)

    # Per-pillar mean shift (V4) — regression detection. Needs pillar data in
    # BOTH releases; older snapshots NULL-fill and are skipped gracefully.
    both_rows = merged[merged["_merge"] == "both"]
    pillar_rows = []
    for label, col in _PILLAR_DIFF:
        a_col, b_col = f"{col}_A", f"{col}_B"
        if a_col in both_rows.columns and b_col in both_rows.columns:
            a_vals, b_vals = both_rows[a_col].dropna(), both_rows[b_col].dropna()
            if not a_vals.empty and not b_vals.empty:
                mean_a, mean_b = both_rows[a_col].mean(), both_rows[b_col].mean()
                pillar_rows.append({
                    "pillar": label,
                    "mean_A": round(mean_a, 2),
                    "mean_B": round(mean_b, 2),
                    "delta": round(mean_b - mean_a, 2),
                })
    st.markdown("#### Per-pillar mean shift (V4)")
    if pillar_rows:
        st.dataframe(pd.DataFrame(pillar_rows), width="stretch", hide_index=True)
    else:
        st.caption("Per-pillar deltas appear once both compared releases carry V4 pillar columns (rebuild required).")

    shifts = merged[merged["_merge"] == "both"].copy()
    if delta_only:
        shifts = shifts[shifts["delta"].abs() > 3]
    shifts = shifts.sort_values("delta", key=lambda series: series.abs(), ascending=False)
    verdict_changes = shifts[shifts["verdict_A"] != shifts["verdict_B"]]

    tab1, tab2 = _safe_tabs(["Score Shifts", "Verdict Changes"])
    with tab1:
        data_table(
            shifts[
                ["dsld_id", "product_name_A", "brand_name_A", "score_A", "score_B", "delta", "verdict_A", "verdict_B"]
            ],
            max_rows=200,
        )
    with tab2:
        data_table(
            verdict_changes[
                ["dsld_id", "product_name_A", "brand_name_A", "verdict_A", "verdict_B", "score_A", "score_B"]
            ],
            max_rows=200,
        )
