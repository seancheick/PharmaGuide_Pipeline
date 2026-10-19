"""Product Trace: every point of one product's score, from the scorer's own receipts."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts.dashboard import shell
from scripts.dashboard.components.theme import KIND_COLORS, PILLAR_COLORS, TOKENS
from scripts.dashboard.components.ui import (
    chips, human, kind_label, kpis, muted, pillar_bars, pillar_state, severity_tone, table,
)
from scripts.dashboard.score_index import PILLAR_LABELS, PILLARS

NO_LINK = "Calibration reference linkage unavailable in this artifact."


def _pick_product(ctx: shell.PageContext) -> str | None:
    products = ctx.frame("products", columns=["dsld_id", "product_name", "brand_name", "total"])
    if products.empty:
        return None
    wanted = st.session_state.get("trace_dsld_id") or st.query_params.get("dsld_id")
    query = st.text_input("Find a product", value="" if not wanted else str(wanted),
                          placeholder="DSLD ID, product name or brand", key="trace_query")
    text = query.strip().lower()
    if text:
        mask = (products["dsld_id"].astype(str).str.lower() == text) \
            | products["product_name"].fillna("").str.lower().str.contains(text, regex=False) \
            | products["brand_name"].fillna("").str.lower().str.contains(text, regex=False)
        matches = products[mask].head(200)
    else:
        matches = products.sort_values("total", ascending=False, na_position="last").head(200)
    if matches.empty:
        st.info("No product matches that search in this run.")
        return None
    labels = {str(r.dsld_id): f"{r.product_name} — {r.brand_name} · {r.dsld_id}" for r in matches.itertuples()}
    ids = list(labels)
    index = ids.index(str(wanted)) if wanted and str(wanted) in ids else 0
    picked = st.selectbox("Product", ids, index=index, format_func=labels.get, key="trace_pick", label_visibility="collapsed")
    st.session_state["trace_dsld_id"] = picked
    st.query_params["dsld_id"] = picked
    return picked


def _composition(row: dict, maxima: dict[str, float]) -> go.Figure:
    """One 100-point capacity bar: each pillar's points, then what it did not earn."""
    fig = go.Figure()
    for pillar in PILLARS:
        score = row.get(f"pillar_{pillar}")
        score = 0.0 if score is None or pd.isna(score) else float(score)
        mx = maxima[pillar]
        fig.add_bar(y=["Score"], x=[score], orientation="h", name=PILLAR_LABELS[pillar],
                    marker={"color": PILLAR_COLORS[pillar], "line": {"color": TOKENS["surface"], "width": 2}},
                    hovertemplate=f"{PILLAR_LABELS[pillar]}: {score:.1f} / {mx:g}<extra></extra>",
                    text=f"{score:.1f}" if score >= 3 else "", textposition="inside", insidetextanchor="middle")
        if mx - score > 0.05:
            fig.add_bar(y=["Score"], x=[mx - score], orientation="h", showlegend=False, name="Not earned",
                        marker={"color": KIND_COLORS["not_earned"], "line": {"color": TOKENS["surface"], "width": 2}},
                        hovertemplate=f"{PILLAR_LABELS[pillar]} not earned: {mx - score:.1f}<extra></extra>")
    fig.update_layout(barmode="stack", height=130, showlegend=False, xaxis={"range": [0, 100], "dtick": 10, "title": None},
                      yaxis={"visible": False}, margin={"l": 4, "r": 4, "t": 30, "b": 4},
                      title={"text": "100-point capacity — grey is not earned", "font": {"size": 14}})
    return fig


def _waterfall(pillar: str, receipts: pd.DataFrame, ledger: dict) -> go.Figure:
    """Each receipt line steps from the running total, coloured by its kind; the last bar is the pillar."""
    rows = receipts.sort_values("seq")
    running = 0.0
    fig = go.Figure()
    seen: set[str] = set()
    for r in rows.itertuples():
        value = float(r.points or 0)
        kind = str(r.kind)
        start, running = running, running + value
        fig.add_bar(x=[str(r.entry_id)], y=[abs(value)], base=[min(start, running)], name=kind_label(kind),
                    legendgroup=kind, showlegend=kind not in seen,
                    marker={"color": KIND_COLORS.get(kind, TOKENS["muted"]), "cornerradius": 4,
                            "line": {"color": TOKENS["surface"], "width": 2}},
                    text=[f"{value:+.2f}"], textposition="outside",
                    hovertemplate=f"{kind_label(kind)} · {r.entry_id}<br>{value:+.4f} → running {running:.2f}<extra></extra>")
        seen.add(kind)
    score = float(ledger.get("score") or 0)
    fig.add_bar(x=["Pillar score"], y=[score], base=[0], name="Pillar score", showlegend=False,
                marker={"color": PILLAR_COLORS[pillar], "cornerradius": 4}, text=[f"{score:.1f}"], textposition="outside",
                hovertemplate=f"Final {PILLAR_LABELS[pillar]}: {score:.1f}<extra></extra>")
    mx = float(ledger.get("max") or 0)
    low = min([0.0] + [float(v or 0) for v in rows["points"]]) if not rows.empty else 0.0
    fig.add_hline(y=mx, line={"color": TOKENS["muted"], "dash": "dot", "width": 1},
                  annotation_text=f"max {mx:g}", annotation_position="top left")
    fig.update_layout(height=360, barmode="overlay", bargap=0.35, margin={"t": 40},
                      legend={"orientation": "h", "y": 1.08, "x": 0},
                      yaxis={"range": [min(0.0, low), max(mx, running) * 1.18 + 0.5], "title": "points"})
    return fig


def _ledger(product: dict, pillar: str) -> None:
    ledgers = product["ledgers"]
    row = ledgers[ledgers["pillar"] == pillar]
    if row.empty:
        st.info(f"No {PILLAR_LABELS[pillar]} ledger: the product has no scored pillars "
                "(suppressed or not scored).")
        return
    ledger = row.iloc[0].to_dict()
    receipts = product["receipts"][product["receipts"]["pillar"] == pillar]
    state = pillar_state(pillar, product["products"].iloc[0].to_dict())
    if state:
        chips([(state, "accent")])
    left, right = st.columns([3, 2])
    with left:
        if receipts.empty:
            st.info("No receipt recorded for this pillar.")
        else:
            st.plotly_chart(_waterfall(pillar, receipts, ledger), width="stretch", key=f"wf_{pillar}")
    with right:
        nominal = float(ledger.get("nominal_deductions") or 0)
        realized = float(ledger.get("realized_deductions") or 0)
        rows = [
            ("Capacity", f"{float(ledger.get('max') or 0):g}"),
            ("Points earned before deductions", f"{float(ledger.get('max') or 0) - float(ledger.get('unawarded') or 0):.2f}"),
            ("Not earned", f"{float(ledger.get('unawarded') or 0):.2f}"),
            ("Nominal deductions", f"{nominal:.2f}"),
            ("Realized deductions", f"{realized:.2f}"),
            ("Absorbed by floors", f"{realized - nominal:.2f}"),
            ("Final pillar score", f"{float(ledger.get('score') or 0):.1f}"),
        ]
        st.dataframe(pd.DataFrame(rows, columns=["Ledger line", "Points"]), hide_index=True, width="stretch")
        if ledger.get("reason"):
            muted(str(ledger["reason"]))
        if ledger.get("entry_sum") is not None and abs(float(ledger["entry_sum"]) - float(ledger["score"] or 0)) > 0.0505:
            st.error(f"Receipt sums to {ledger['entry_sum']} but the pillar is {ledger['score']} — see the Audit Queue.")
    if not receipts.empty:
        display = receipts.sort_values("seq").assign(type=lambda d: d["kind"].map(kind_label))[
            ["entry_id", "type", "points", "raw", "source", "basis", "withheld_by"]]
        for column in ("source", "basis", "withheld_by"):
            display[column] = display[column].astype(object).where(display[column].notna(), "")
        st.dataframe(display, hide_index=True, width="stretch",
                     column_config={"points": st.column_config.NumberColumn(format="%+.4f"),
                                    "raw": st.column_config.NumberColumn(format="%.4f")})


def _timeline(ctx: shell.PageContext, dsld_id: str) -> pd.DataFrame:
    rows = []
    for run in ctx.index.runs():
        products = ctx.frame("products", run["run_key"], ["dsld_id", "total", "tier", "product_safety_status",
                                                          *[f"pillar_{p}" for p in PILLARS]])
        hit = products[products["dsld_id"] == dsld_id]
        if not hit.empty:
            rows.append({"run_time": run.get("run_time"), "plane": run["plane"], "fidelity": run["fidelity"],
                         "config": ", ".join(v for v in run.get("config_versions") or [] if v),
                         **hit.iloc[0].drop("dsld_id").to_dict()})
    return pd.DataFrame(rows)


def render(ctx: shell.PageContext) -> None:
    if not shell.banner(ctx):
        return
    dsld_id = _pick_product(ctx)
    if not dsld_id:
        return
    product = ctx.index.product(ctx.run_key, dsld_id)
    if product["products"].empty:
        st.warning("This product is not in the selected run.")
        return
    row = product["products"].iloc[0].to_dict()

    st.subheader(f"{row.get('product_name')}")
    chips([(row.get("brand_name") or "—", ""), (f"DSLD {dsld_id}", ""), (f"route {row.get('module')}", ""),
           (f"category {row.get('category')}", ""), (f"config {row.get('config_version') or '—'}", "accent")])
    safety = row.get("product_safety_status")
    kpis([
        ("Score", "—" if pd.isna(row.get("total")) else f"{row['total']:.1f} / 100",
         "Sum of the six pillars as recorded by the scorer"),
        ("Tier", row.get("tier") or "—", "Quality tier — never a safety verdict"),
        ("Safety", human(safety), "product_safety_status: consumer safety, separate from quality"),
        ("Assessment", human(row.get("quality_assessment_status")), "Partial means PharmaGuide's own review is unfinished"),
        ("Confidence", human(row.get("confidence")), "Score confidence band"),
    ])
    if row.get("quality_score_status") != "scored":
        reasons = [row.get(k) for k in ("blocking_reason", "suppressed_reason", "score_unavailable_reason",
                                        "not_scorable_reason", "safety_signal_reason") if row.get(k)]
        st.warning(f"{human(row.get('quality_score_status'))}: {' · '.join(map(str, dict.fromkeys(reasons))) or 'no reason recorded'}",
                   icon=":material/block:")

    st.plotly_chart(_composition(row, ctx.maxima), width="stretch", key="composition")
    pillar_bars(row, ctx.maxima)

    st.markdown("#### Pillar ledgers")
    tabs = st.tabs([PILLAR_LABELS[p] for p in PILLARS])
    for tab, pillar in zip(tabs, PILLARS):
        with tab:
            _ledger(product, pillar)
    muted(NO_LINK)

    st.markdown("#### Gates, dose safety and additives")
    g1, g2 = st.columns(2)
    with g1:
        flags = product["dose_flags"]
        st.caption("Dose safety evaluation (exposure that triggered a ceiling is marked)")
        table(flags[["state", "nutrient", "pct_ul", "pct_ul_at_minimum", "is_ceiling", "ceiling_kind", "ul", "ul_unit",
                     "reason"]] if not flags.empty else flags, key="trace_flags", name=f"dose_flags_{dsld_id}",
              run_key=ctx.run_key, height=220)
        missing = list(row.get("completeness_missing") if row.get("completeness_missing") is not None else [])
        st.caption(f"Completeness gate — missing: {', '.join(missing) or 'none'} · score cap: "
                   f"{row.get('completeness_score_cap') if pd.notna(row.get('completeness_score_cap')) else 'none'} · "
                   f"safety signals: {', '.join(list(row.get('safety_signals') if row.get('safety_signals') is not None else [])) or 'none'}")
    with g2:
        additives = product["additives"]
        st.caption("Additive and sweetener penalty lines (Formula checks)")
        table(additives, key="trace_additives", name=f"additives_{dsld_id}", run_key=ctx.run_key, height=220)
    st.caption("Dose references (% of RDA/AI and of the upper limit, per ingredient)")
    table(product["dose_refs"].drop(columns=["dsld_id"]), key="trace_refs", name=f"dose_refs_{dsld_id}",
          run_key=ctx.run_key, height=260)

    findings = ctx.index.findings()
    mine = findings[(findings["dsld_id"] == dsld_id) & (findings["plane"] == ctx.plane)] if not findings.empty else findings
    st.markdown("#### Findings for this product")
    if mine.empty:
        st.caption("No findings.")
    else:
        chips((f"{r.severity}: {r.message}", severity_tone(r.severity)) for r in mine.itertuples())

    st.markdown("#### Across runs and planes")
    timeline = _timeline(ctx, dsld_id)
    if not timeline.empty:
        fig = go.Figure()
        for plane, group in timeline.groupby("plane"):
            fig.add_scatter(x=pd.to_datetime(group["run_time"], utc=True, errors="coerce"), y=group["total"],
                            mode="lines+markers", name=plane, line={"width": 2}, marker={"size": 8})
        fig.update_layout(height=240, title={"text": "Score over time", "font": {"size": 14}},
                          yaxis={"range": [0, 100], "title": None})
        st.plotly_chart(fig, width="stretch", key="trace_timeline")
        table(timeline, key="trace_timeline_table", name=f"timeline_{dsld_id}", run_key=ctx.run_key, height=200)

    with st.expander("Compare with another product", icon=":material/compare:"):
        other = st.text_input("Second product DSLD ID", key="trace_other")
        if other:
            second = ctx.index.product(ctx.run_key, other.strip())["products"]
            if second.empty:
                st.info("Not in this run.")
            else:
                cols = ["total", "tier", *[f"pillar_{p}" for p in PILLARS], "product_safety_status", "evidence_state", "dose_basis"]
                both = pd.concat([product["products"][cols].assign(product=dsld_id), second[cols].assign(product=other.strip())])
                st.dataframe(both.set_index("product").T, width="stretch")

    explain = {name: frame.to_dict("records") for name, frame in product.items() if isinstance(frame, pd.DataFrame)}
    explain["slim"] = product.get("slim")
    explain["run"] = ctx.run
    st.download_button("Download explain JSON", json.dumps(explain, default=str, indent=2),
                       file_name=f"explain_{dsld_id}__{ctx.run_key}.json", mime="application/json",
                       icon=":material/download:")
