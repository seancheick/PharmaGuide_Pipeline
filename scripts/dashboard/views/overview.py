"""Overview: run health, catalog KPIs, candidate-vs-release parity, top findings, drift."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts.dashboard import shell
from scripts.dashboard.components.theme import TOKENS
from scripts.dashboard.components.ui import chips, human, kpis, table
from scripts.dashboard.findings_rules import SEVERITY_ORDER, psi
from scripts.dashboard.run_compare import summarize
from scripts.dashboard.score_index import PILLAR_LABELS, PILLARS
from scripts.dashboard.time_format import format_dashboard_datetime

TIER_ORDER = ["Exceptional", "Excellent", "Very good", "Good", "Needs improvement", "Poor"]
# Tier is ordinal quality (never safety): one sequential hue, dark = higher tier.
TIER_COLORS = ["#183B3F", "#2E6E72", "#468387", "#80ADB0", "#BCD3D4", "#DCE7E7"]


def status_counts(products: pd.DataFrame) -> dict[str, int]:
    scored = products["quality_score_status"] == "scored"
    return {
        "products": len(products),
        "scored": int(scored.sum()),
        "partial": int((scored & (products["quality_assessment_status"] == "partial")).sum()),
        "not_scored": int((products["quality_score_status"] == "not_scored").sum()),
        "suppressed": int((products["quality_score_status"] == "suppressed_safety").sum()),
        "blocked": int((products["product_safety_status"] == "blocked").sum()),
        "caution": int((products["product_safety_status"] == "caution").sum()),
    }


def _health_strip(ctx: shell.PageContext) -> None:
    data = ctx.data
    manifest = data.export_manifest or {}
    integrity = manifest.get("integrity") or {}
    candidate = ctx.index.run(ctx.index.latest("candidate")) or {}
    release = ctx.index.run(ctx.index.latest("release")) or {}
    stages = [
        ("Clean / enrich", format_dashboard_datetime(data.latest_enriched_at, style="compact"),
         f"{integrity.get('enriched_input_count', '—'):,}" if isinstance(integrity.get("enriched_input_count"), int) else "—",
         "enriched products in the last release"),
        ("Score (candidate)", format_dashboard_datetime(candidate.get("run_time"), style="compact"),
         f"{candidate.get('products', 0):,}", f"{len(candidate.get('parts') or {})} brand batches"),
        ("Release (catalog)", format_dashboard_datetime(release.get("run_time"), style="compact"),
         f"{release.get('products', 0):,}", f"schema {release.get('export_schema_version') or '—'}"),
        ("Dashboard index", format_dashboard_datetime(ctx.index.meta.get("built_at"), style="compact"),
         f"{ctx.index.meta.get('refresh_seconds', '—')} s", "last refresh time"),
    ]
    cols = st.columns(len(stages))
    for col, (name, when, volume, note) in zip(cols, stages):
        with col.container(border=True):
            st.caption(name)
            st.markdown(f"**{volume}**")
            st.caption(f"{when} · {note}")


def render(ctx: shell.PageContext) -> None:
    if not shell.banner(ctx):
        return
    products = ctx.products()
    counts = status_counts(products)
    findings = ctx.index.findings()
    open_counts = findings["severity"].value_counts().to_dict() if not findings.empty else {}
    scored = products[(products["quality_score_status"] == "scored")]
    kpis([
        ("Products", f"{counts['products']:,}", None),
        ("Scored", f"{counts['scored']:,}", "quality_score_status = scored"),
        ("Partial", f"{counts['partial']:,}", "Scored, but PharmaGuide's own assessment is unfinished"),
        ("Not scored", f"{counts['not_scored']:,}", None),
        ("Suppressed", f"{counts['suppressed']:,}", "Blocked for safety; ships with its reason"),
        ("Median score", f"{scored['total'].median():.1f}" if not scored.empty else "—", "Scored products"),
        ("Critical findings", f"{open_counts.get('critical', 0):,}", "Integrity defects and unexplained changes"),
    ], per_row=7)

    _health_strip(ctx)

    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Tier mix")
        fig = go.Figure()
        planes = [("Candidate", ctx.index.latest("candidate")), ("Release", ctx.index.latest("release"))]
        for tier, color in zip(TIER_ORDER, TIER_COLORS):
            xs, ys = [], []
            for label, key in planes:
                if not key:
                    continue
                frame = ctx.products(key)
                n = int((frame["tier"] == tier).sum())
                xs.append(n)
                ys.append(label)
            fig.add_bar(x=xs, y=ys, orientation="h", name=tier, marker={"color": color, "line": {"color": TOKENS["surface"], "width": 2}},
                        hovertemplate=f"{tier}: %{{x:,}}<extra></extra>")
        fig.update_layout(barmode="stack", height=250, xaxis={"title": "products"}, margin={"t": 70},
                          legend={"orientation": "h", "y": 1.25, "x": 0, "traceorder": "normal"})
        st.plotly_chart(fig, width="stretch", key="tier_mix")
    with right:
        st.markdown("#### Candidate vs release")
        cand, rel = ctx.index.latest("candidate"), ctx.index.latest("release")
        if cand and rel:
            summary = summarize(ctx.deltas(rel, cand))
            cand_run, rel_run = ctx.index.run(cand), ctx.index.run(rel)
            chips([(f"release {', '.join(rel_run.get('config_versions') or [])}", ""),
                   (f"candidate {', '.join(cand_run.get('config_versions') or [])}", "accent")])
            kpis([("Moved", f"{summary.get('moved', 0):,}", "Score changed"),
                  ("Tier crossed", f"{summary.get('tier_crossed', 0):,}", None),
                  ("Safety changed", f"{summary.get('safety_changed', 0):,}", "Every one needs review"),
                  ("Unexplained", f"{summary.get('unexplained', 0):,}", "No pillar or run-level cause")], per_row=2)
            if st.button("Open run compare", icon=":material/compare_arrows:"):
                shell.go("run-compare")
        else:
            st.caption("Needs both a candidate and a release run in the index.")

    st.markdown("#### Top findings")
    if findings.empty:
        st.success("No findings in the latest runs.", icon=":material/check_circle:")
    else:
        top = (findings.groupby(["severity", "rule_id", "message", "plane"]).size().rename("products").reset_index())
        top["order"] = top["severity"].map({s: i for i, s in enumerate(SEVERITY_ORDER)})
        top = top.sort_values(["order", "products"], ascending=[True, False]).drop(columns="order")
        table(top, key="overview_findings", name="findings_summary", run_key=ctx.run_key, height=260)
        if st.button("Open the audit queue", icon=":material/flag:"):
            shell.go("audit-queue")

    st.markdown("#### Pillar drift")
    base = ctx.baseline_key()
    if base:
        before, after = ctx.products(base), products
        rows = [{"pillar": PILLAR_LABELS[p], "PSI": round(psi(before[f"pillar_{p}"], after[f"pillar_{p}"], cap=ctx.maxima[p]), 3),
                 "baseline mean": round(before[f"pillar_{p}"].mean(), 2), "current mean": round(after[f"pillar_{p}"].mean(), 2)}
                for p in PILLARS]
        st.caption(f"Against {human((ctx.index.run(base) or {}).get('plane'))} run · PSI above 0.2 is a material shift")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                     column_config={"PSI": st.column_config.ProgressColumn(min_value=0.0, max_value=0.5, format="%.3f")})
