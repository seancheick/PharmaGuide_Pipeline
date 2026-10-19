"""Safety & Regulatory: blocked/suppressed with reasons, upper-limit findings, CAERS, safety copy.

Banned and recalled products always ship with their reason; this page lists them all.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from scripts.dashboard import shell
from scripts.dashboard.components.ui import human, kpis, table
from scripts.dashboard.views.audit_caers import render_audit_caers
from scripts.dashboard.views.safety_copy import render_safety_copy

REASON_COLUMNS = ["blocking_reason", "suppressed_reason", "safety_signal_reason", "score_unavailable_reason"]


def render(ctx: shell.PageContext) -> None:
    if not shell.banner(ctx):
        return
    products = ctx.products()
    flags = ctx.frame("dose_flags")
    blocked = products[(products["product_safety_status"] == "blocked") | (products["quality_score_status"] == "suppressed_safety")]
    caution = products[products["product_safety_status"] == "caution"]
    over_ul = flags[flags["state"] == "confirmed_over_threshold"] if not flags.empty else flags
    kpis([("Blocked / suppressed", f"{len(blocked):,}", "Always shipped with their reason"),
          ("Caution", f"{len(caution):,}", None),
          ("Confirmed over upper limit", f"{over_ul['dsld_id'].nunique() if not over_ul.empty else 0:,}", "Products"),
          ("Dose ceiling applied", f"{int(products['dose_cap_applied'].fillna(False).astype(bool).sum()):,}", None)])

    tabs = st.tabs(["Blocked & suppressed", "Caution signals", "Upper-limit findings", "CAERS signals", "Safety copy"])
    with tabs[0]:
        columns = ["dsld_id", "product_name", "brand_name", "product_safety_status", "quality_score_status", *REASON_COLUMNS]
        missing = blocked[blocked[REASON_COLUMNS[:3]].isna().all(axis=1)]
        if not missing.empty:
            st.error(f"{len(missing)} blocked product(s) have no recorded reason — see the Audit Queue.")
        picked = table(blocked[columns], key="sf_blocked", name="blocked_suppressed", run_key=ctx.run_key, select=True, height=420)
        if picked:
            shell.go("product-trace", trace_dsld_id=str(blocked[columns].iloc[picked[0]]["dsld_id"]))
    with tabs[1]:
        signals = caution.explode("safety_signals")
        counts = signals.groupby("safety_signals", dropna=False).size().rename("products").reset_index()
        counts["safety_signals"] = counts["safety_signals"].fillna("(none recorded)").map(lambda s: human(s))
        st.dataframe(counts.sort_values("products", ascending=False), hide_index=True, width="stretch")
        table(caution[["dsld_id", "product_name", "brand_name", "safety_signals", "safety_signal_reason", "total", "tier"]],
              key="sf_caution", name="caution_products", run_key=ctx.run_key, height=360)
    with tabs[2]:
        if flags.empty:
            st.info("No dose-safety records in this run.")
        else:
            by_nutrient = flags[flags["state"] != "dose_ceiling"].groupby(["nutrient", "state"], dropna=False).agg(
                products=("dsld_id", "nunique"), max_pct_ul=("pct_ul", "max")).reset_index()
            table(by_nutrient.sort_values("products", ascending=False), key="sf_ul_summary", name="ul_by_nutrient",
                  run_key=ctx.run_key, height=300)
            ceilings = flags[flags["is_ceiling"].fillna(False).astype(bool)].merge(
                products[["dsld_id", "product_name", "brand_name", "pillar_dose"]], on="dsld_id", how="left")
            table(ceilings[["dsld_id", "product_name", "brand_name", "nutrient", "pct_ul", "pct_ul_at_minimum", "ceiling_kind",
                            "ul", "ul_unit", "cap_public", "pillar_dose"]], key="sf_ceilings", name="dose_ceilings",
                  run_key=ctx.run_key, height=360,
                  caption="The ingredient and exposure that set each product's Dose safety ceiling (PharmaGuide scoring "
                          "policy, not a medical toxicity grade).")
    with tabs[3]:
        render_audit_caers(ctx.data)
    with tabs[4]:
        render_safety_copy(ctx.data)
