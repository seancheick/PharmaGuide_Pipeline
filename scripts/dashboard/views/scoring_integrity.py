"""Scoring Integrity — automated V4 scoring-anomaly detection.

Three checks, each catching a class of scoring bug:

  1. Reconciliation — the six pillars must sum to quality_score_v4_100.
     A deviation means calibration/anchoring/scorer drift.
  2. Zero pillars — verification is the ONLY fail-open pillar (neutral_baseline
     6.0), so a verification == 0 is a true anomaly worth alerting on. The other
     five pillars (formulation, dose, evidence, transparency, safety_hygiene)
     legitimately reach 0 — basic forms, off-range dose, no clinical evidence,
     an opaque blend, or a flagged ingredient — so those zeros are low scores,
     not bugs. The view splits the two so the catalog's genuinely-low products
     don't read as false alarms.
  3. Out-of-range / impossible — pillar > max, pillar < 0, total outside
     [0,100], or status='scored' while a pillar is NULL.

The detection functions are PURE (DataFrame -> DataFrame) so they are unit-tested
without a populated DB. The view only renders their output.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from scripts.dashboard.components.score_breakdown import V4_PILLARS
from scripts.dashboard.data_loader import filter_product_catalog

RECON_TOLERANCE = 0.1
PILLAR_COLS = [col for _lbl, col, _mx in V4_PILLARS]

# Verification is the only pillar that fails open to a neutral non-zero baseline
# (6.0), so a verification == 0 is a true anomaly. Every other pillar can
# legitimately score 0 (a real low score), so a 0 there is not a bug.
FAIL_OPEN_PILLAR_COLS = {"pillar_verification_v4"}


def pillars_present(df: pd.DataFrame) -> bool:
    """True when at least one pillar column carries data (post-rebuild)."""
    return any(c in df.columns and df[c].notna().any() for c in PILLAR_COLS)


def find_reconciliation_mismatches(df: pd.DataFrame, tolerance: float = RECON_TOLERANCE) -> pd.DataFrame:
    """Rows where sum(pillars) deviates from quality_score_v4_100 by > tolerance.
    Considers only rows with all six pillars and the total present."""
    if df.empty or "quality_score_v4_100" not in df.columns:
        return df.iloc[0:0]
    cols = [c for c in PILLAR_COLS if c in df.columns]
    if len(cols) < len(PILLAR_COLS):
        return df.iloc[0:0]
    sub = df.dropna(subset=cols + ["quality_score_v4_100"]).copy()
    if sub.empty:
        return sub
    sub["pillar_sum"] = sub[cols].sum(axis=1).round(2)
    sub["recon_delta"] = (sub["pillar_sum"] - sub["quality_score_v4_100"]).round(3)
    return sub[sub["recon_delta"].abs() > tolerance]


def find_zero_pillars(df: pd.DataFrame) -> pd.DataFrame:
    """Long-form (product, pillar) frame where a pillar == 0 exactly.

    Each row carries `is_anomaly`: True only for fail-open pillars (verification),
    where 0 should never occur; False for pillars that legitimately reach 0.
    """
    rows = []
    for lbl, col, mx in V4_PILLARS:
        if col not in df.columns:
            continue
        for _, r in df[df[col] == 0].iterrows():
            rows.append({
                "dsld_id": r.get("dsld_id"),
                "product_name": r.get("product_name"),
                "brand_name": r.get("brand_name"),
                "v4_module": r.get("v4_module"),
                "pillar": lbl,
                "max": mx,
                "total_v4": r.get("score_v4", r.get("score")),
                "is_anomaly": col in FAIL_OPEN_PILLAR_COLS,
            })
    return pd.DataFrame(rows)


def find_out_of_range(df: pd.DataFrame) -> pd.DataFrame:
    """Rows with impossible values, annotated with an `issues` column."""
    if df.empty:
        return df.iloc[0:0]
    issues = pd.Series(False, index=df.index)
    reasons: dict = {i: [] for i in df.index}

    for lbl, col, mx in V4_PILLARS:
        if col not in df.columns:
            continue
        over = (df[col] > mx).fillna(False)
        under = (df[col] < 0).fillna(False)
        for i in df.index[over]:
            reasons[i].append(f"{lbl} > {mx}")
        for i in df.index[under]:
            reasons[i].append(f"{lbl} < 0")
        issues = issues | over | under

    if "quality_score_v4_100" in df.columns:
        oob = ((df["quality_score_v4_100"] < 0) | (df["quality_score_v4_100"] > 100)).fillna(False)
        for i in df.index[oob]:
            reasons[i].append("total outside [0,100]")
        issues = issues | oob

    if "quality_score_status" in df.columns and pillars_present(df):
        scored = df["quality_score_status"].fillna("") == "scored"
        for lbl, col, mx in V4_PILLARS:
            if col not in df.columns:
                continue
            null_pillar = df[col].isna() & scored
            for i in df.index[null_pillar]:
                reasons[i].append(f"scored but {lbl} is NULL")
            issues = issues | null_pillar

    out = df[issues].copy()
    if out.empty:
        return out
    out["issues"] = [", ".join(reasons[i]) for i in out.index]
    return out


def render_scoring_integrity(data):
    """Tier-1 anomaly dashboard: reconciliation, zero-pillars, out-of-range."""
    st.subheader("Scoring Integrity (V4 anomaly detection)")
    frame = filter_product_catalog(data)
    st.caption(
        f"Rows in scope: {0 if frame.empty else len(frame):,}. Three invariant "
        "checks — green means no anomalies found."
    )
    if frame.empty:
        st.warning("No products in scope.")
        return
    if not pillars_present(frame):
        st.info(
            "V4 pillar columns are empty in this build, so reconciliation and "
            "zero-pillar checks can't run yet. Rebuild the catalog "
            "(`scripts/rebuild_dashboard_snapshot.sh`) and reload. "
            "Out-of-range checks on the total score still run below."
        )

    recon = find_reconciliation_mismatches(frame)
    zeros = find_zero_pillars(frame)
    oor = find_out_of_range(frame)

    # Split zeros: verification-0 is a true anomaly; every other pillar-0 is a
    # legitimately low score (not a bug), so they must not read as false alarms.
    if zeros.empty:
        verif_zeros, low_zeros = zeros, zeros
    else:
        verif_zeros = zeros[zeros["is_anomaly"]]
        low_zeros = zeros[~zeros["is_anomaly"]]

    c1, c2, c3 = st.columns(3)
    c1.metric("Reconciliation mismatches", f"{len(recon):,}", help="sum(pillars) != quality_score_v4_100")
    c2.metric("Verification = 0 (anomaly)", f"{len(verif_zeros):,}", help="verification fails open to 6.0, so 0 should never occur")
    c3.metric("Out-of-range / impossible", f"{len(oor):,}", help="pillar>max, <0, total off-range, or scored-but-NULL")

    st.divider()

    st.markdown("#### 1. Pillar ↔ total reconciliation")
    if recon.empty:
        st.success("All scored products: the six pillars sum to quality_score_v4_100. ✅")
    else:
        st.error(f"{len(recon):,} products where pillars don't sum to the total — investigate the scorer/calibration.")
        cols = [c for c in ["dsld_id", "product_name", "brand_name", "v4_module", "pillar_sum", "quality_score_v4_100", "recon_delta"] if c in recon.columns]
        st.dataframe(recon[cols].sort_values("recon_delta", key=lambda s: s.abs(), ascending=False), width="stretch", hide_index=True)

    st.divider()
    st.markdown("#### 2. Pillars scoring exactly 0")

    st.markdown("**Verification = 0 — anomaly**")
    if verif_zeros.empty:
        st.success("No product scored 0 on verification — none expected (it fails open to 6.0). ✅")
    else:
        st.error(
            f"{len(verif_zeros):,} products scored 0 on verification — this should never happen "
            "(verification fails open to 6.0). Investigate a large quality-system violation "
            "penalty or a scorer bug."
        )
        vcols = [c for c in ["dsld_id", "product_name", "brand_name", "v4_module", "total_v4"] if c in verif_zeros.columns]
        st.dataframe(verif_zeros[vcols], width="stretch", hide_index=True)

    st.markdown("**Other pillars = 0 — legitimately low, not bugs**")
    if low_zeros.empty:
        st.info("No formulation / dose / evidence / transparency / safety-hygiene pillar scored 0.")
    else:
        by_pillar = low_zeros.groupby("pillar").size().reset_index(name="count")
        st.caption(
            "These pillars legitimately reach 0 — basic forms, off-range dose, no clinical "
            "evidence, an opaque blend, or a flagged ingredient. This is a weakest-pillar "
            "investigation list, not a bug list. Count by pillar:"
        )
        st.dataframe(by_pillar, width="stretch", hide_index=True)
        with st.expander(f"Affected products ({len(low_zeros):,})"):
            lcols = [c for c in ["dsld_id", "product_name", "brand_name", "v4_module", "pillar", "max", "total_v4"] if c in low_zeros.columns]
            st.dataframe(low_zeros[lcols], width="stretch", hide_index=True)

    st.divider()
    st.markdown("#### 3. Out-of-range / impossible values")
    if oor.empty:
        st.success("No out-of-range or impossible scores. ✅")
    else:
        st.error(f"{len(oor):,} products with impossible values — hard bug signal.")
        cols = [c for c in ["dsld_id", "product_name", "brand_name", "v4_module", "quality_score_status", "score_v4", "issues"] if c in oor.columns]
        st.dataframe(oor[cols], width="stretch", hide_index=True)
