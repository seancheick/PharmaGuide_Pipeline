"""Product Explorer: every product, six pillar bars, any filter, click through to the trace."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from scripts.dashboard import shell
from scripts.dashboard.components.ui import (
    DOSE_BASIS_LABELS, EVIDENCE_STATE_LABELS, human, kpis, pillar_column_config, table,
)
from scripts.dashboard.saved_views import SAVED_VIEWS, apply_filters, attach_comparison
from scripts.dashboard.score_index import PILLAR_LABELS, PILLARS

COLUMNS = ["dsld_id", "product_name", "brand_name", "total", "tier", *[f"pillar_{p}" for p in PILLARS],
           "quality_assessment_status", "product_safety_status", "quality_score_status", "confidence", "module",
           "category", "alerts", "config_version"]


def explorer_frame(ctx: shell.PageContext) -> pd.DataFrame:
    products = ctx.products()
    if products.empty:
        return products
    findings = ctx.index.findings()
    if not findings.empty:
        counts = findings[findings["run_key"] == ctx.run_key].groupby("dsld_id").size().rename("alerts")
        products = products.join(counts, on="dsld_id")
    products["alerts"] = products.get("alerts", pd.Series(0, index=products.index)).fillna(0).astype(int)
    release = ctx.products(ctx.index.latest("release")) if ctx.plane == "candidate" and ctx.index.latest("release") else None
    return attach_comparison(products, ctx.deltas(ctx.baseline_key(), ctx.run_key), release=release)


def _options(frame: pd.DataFrame, column: str) -> list:
    return sorted(value for value in frame[column].dropna().unique().tolist())


def render(ctx: shell.PageContext) -> None:
    if not shell.banner(ctx):
        return
    frame = explorer_frame(ctx)
    if frame.empty:
        st.info("This run has no products.")
        return

    top = st.columns([3, 2])
    view = top[0].pills("Saved audit views", list(SAVED_VIEWS), selection_mode="single", key="explorer_view",
                        help="Audit states, not defects — anomalies live in the Audit Queue.")
    search = top[1].text_input("Search", placeholder="DSLD ID, product or brand", key="explorer_search")
    spec: dict = dict(SAVED_VIEWS.get(view, {})) if view else {}
    if search:
        spec["search"] = search

    with st.expander("Filters", icon=":material/filter_list:", expanded=False):
        row = st.columns(4)
        lo, hi = row[0].slider("Overall score", 0.0, 100.0, (0.0, 100.0), 0.5, key="f_score")
        if (lo, hi) != (0.0, 100.0):
            spec.update(score_min=lo, score_max=hi)
        spec["tier"] = row[1].multiselect("Tier", _options(frame, "tier"), key="f_tier")
        spec["quality_score_status"] = spec.get("quality_score_status") or row[2].multiselect(
            "Score status", _options(frame, "quality_score_status"), format_func=human, key="f_status")
        spec["product_safety_status"] = row[3].multiselect("Safety status", _options(frame, "product_safety_status"),
                                                           format_func=human, key="f_safety")
        row = st.columns(4)
        spec["quality_assessment_status"] = spec.get("quality_assessment_status") or row[0].multiselect(
            "Assessment", _options(frame, "quality_assessment_status"), format_func=human, key="f_assess")
        spec["module"] = row[1].multiselect("Route", _options(frame, "module"), key="f_module")
        spec["category"] = row[2].multiselect("Category", _options(frame, "category"), key="f_category")
        spec["brand_name"] = row[3].multiselect("Brand", _options(frame, "brand_name"), key="f_brand")

        st.caption("Pillars")
        ranges, zeros = {}, []
        cols = st.columns(len(PILLARS))
        for col, pillar in zip(cols, PILLARS):
            mx = ctx.maxima[pillar]
            sel = col.slider(PILLAR_LABELS[pillar], 0.0, float(mx), (0.0, float(mx)), 0.1, key=f"f_p_{pillar}")
            if sel != (0.0, float(mx)):
                ranges[pillar] = sel
            if col.checkbox("= 0", key=f"f_p_{pillar}_zero"):
                zeros.append(pillar)
        if ranges:
            spec["pillar_range"] = {**spec.get("pillar_range", {}), **ranges}
        if zeros:
            spec["pillar_zero"] = sorted(set(spec.get("pillar_zero", [])) | set(zeros))

        row = st.columns(3)
        spec["evidence_state"] = spec.get("evidence_state") or row[0].multiselect(
            "Evidence state", _options(frame, "evidence_state"), format_func=lambda s: EVIDENCE_STATE_LABELS.get(s, s),
            key="f_evstate")
        spec["dose_basis"] = row[1].multiselect("Dose basis", _options(frame, "dose_basis"),
                                                format_func=lambda s: DOSE_BASIS_LABELS.get(s, s), key="f_dose")
        spec["verification_tier"] = row[2].multiselect("Verification tier", _options(frame, "verification_tier"),
                                                       key="f_vtier")
        entry_ids = sorted({entry for ids in frame["receipt_entry_ids"].dropna() for entry in list(ids)})
        row = st.columns([3, 1])
        picked = row[0].multiselect("Receipt line present (any of)", entry_ids, key="f_entries")
        if picked:
            spec["entry_ids"] = picked
        unawarded = row[1].number_input("Not earned ≥", 0.0, 100.0, 0.0, 1.0, key="f_unawarded")
        if unawarded:
            spec["unawarded_min"] = unawarded
        toggles = st.columns(7)
        for col, (key, label) in zip(toggles, [("has_deduction", "Deduction"), ("has_cap", "Cap"),
                                               ("has_floor", "Floor"), ("has_neutral", "Neutral"),
                                               ("dose_cap", "Dose ceiling"), ("verification_fail_open", "Verif. unknown"),
                                               ("unmapped", "Unmapped active")]):
            if col.checkbox(label, key=f"f_t_{key}"):
                spec[key] = True
        row = st.columns(3)
        at_max = row[0].multiselect("Pillars at maximum", PILLARS, format_func=PILLAR_LABELS.get, key="f_at_max")
        neutral = row[1].multiselect("Neutral-only pillars", PILLARS, format_func=PILLAR_LABELS.get, key="f_neutral")
        spec["evidence_display_state"] = row[2].multiselect(
            "Evidence display state", _options(frame, "evidence_display_state"), key="f_display")
        if at_max:
            spec["pillar_at_max"] = {p: ctx.maxima[p] for p in at_max}
        if neutral:
            spec["pillar_neutral"] = neutral
        row = st.columns(3)
        spec["confidence"] = spec.get("confidence") or row[0].multiselect("Score confidence", _options(frame, "confidence"), key="f_confidence")
        spec["route_confidence"] = spec.get("route_confidence") or row[1].multiselect("Route confidence", _options(frame, "route_confidence"), key="f_route_confidence")
        spec["config_version"] = row[2].multiselect("Config version", _options(frame, "config_version"), key="f_config")
        if st.checkbox("High total with a low pillar", key="f_high_low"):
            spec["high_total_low_pillar"] = ctx.maxima
        if st.checkbox("Missing provenance", key="f_missing_provenance"):
            spec["missing_provenance"] = True
        if st.checkbox("Deduction fully absorbed by a floor", key="f_absorbed"):
            spec["fully_absorbed"] = True

    filtered = apply_filters(frame, {k: v for k, v in spec.items() if v not in (None, [], "")})
    scored = filtered[filtered["quality_score_status"] == "scored"]
    kpis([
        ("Products", f"{len(filtered):,} / {len(frame):,}", "Matching the current view and filters"),
        ("Median score", f"{scored['total'].median():.1f}" if not scored.empty else "—", "Scored products only"),
        ("Partial", f"{(filtered['quality_assessment_status'] == 'partial').sum():,}", "Assessment not complete"),
        ("With alerts", f"{(filtered['alerts'] > 0).sum():,}", "Products with at least one finding"),
    ])
    picked_rows = table(
        filtered[COLUMNS].sort_values("total", ascending=False, na_position="last"),
        key="explorer_table", name=f"explorer_{(view or 'all').replace(' ', '_')}", run_key=ctx.run_key, select=True,
        height=560, caption="Select a row to open its trace.",
        column_config={
            **pillar_column_config(ctx.maxima),
            "dsld_id": st.column_config.TextColumn("DSLD", width="small"),
            "product_name": st.column_config.TextColumn("Product", width="large"),
            "brand_name": "Brand",
            "total": st.column_config.NumberColumn("Score", format="%.1f"),
            "alerts": st.column_config.NumberColumn("Alerts", help="Findings for this product in the Audit Queue"),
        },
    )
    if picked_rows:
        ordered = filtered[COLUMNS].sort_values("total", ascending=False, na_position="last").reset_index(drop=True)
        shell.go("product-trace", trace_dsld_id=str(ordered.iloc[picked_rows[0]]["dsld_id"]))
