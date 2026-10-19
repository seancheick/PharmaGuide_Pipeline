"""Run Compare & Trends: candidate review against a baseline, and history across runs."""

from __future__ import annotations

import json
from collections import Counter

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts.dashboard import shell
from scripts.dashboard.components.theme import PILLAR_COLORS, TOKENS
from scripts.dashboard.components.ui import kpis, table
from scripts.dashboard.run_compare import MOVE_EPS, config_diff, run_level_causes, summarize
from scripts.dashboard.score_index import PILLAR_LABELS, PILLARS
from scripts.dashboard.time_format import format_dashboard_datetime

PROVENANCE_FIELDS = [
    ("plane", "Plane"), ("run_time", "Source time"), ("fidelity", "Fidelity"), ("products", "Products"),
    ("config_versions", "Config versions"), ("artifact_stage_code_fingerprints", "Stage code (artifact)"),
    ("artifact_reference_data_fingerprints", "Reference data (artifact)"), ("export_schema_version", "Export schema"),
    ("db_version", "Catalog version"), ("source", "Source"), ("run_key", "Run key"),
]


def _label(run: dict) -> str:
    return (f"{run['plane']} · {format_dashboard_datetime(run.get('run_time'), style='compact')} · "
            f"{', '.join(v.split('-')[0] for v in run.get('config_versions') or [] if v) or '?'}")


def render(ctx: shell.PageContext) -> None:
    if not shell.banner(ctx):
        return
    runs = list(reversed(ctx.index.runs()))
    if len(runs) < 2:
        st.info("Run compare needs at least two runs in the index (for example the candidate and the release).")
        return
    keys = [run["run_key"] for run in runs]
    labels = {run["run_key"]: _label(run) for run in runs}
    base_default = ctx.baseline_key() or next(key for key in keys if key != ctx.run_key)
    cols = st.columns(2)
    base = cols[0].selectbox("Baseline", keys, index=keys.index(base_default) if base_default in keys else 0,
                             format_func=labels.get, key=f"rc_base_{ctx.run_key}")
    cand = cols[1].selectbox("Candidate", keys, index=keys.index(ctx.run_key) if ctx.run_key in keys else 0,
                             format_func=labels.get, key=f"rc_cand_{ctx.run_key}")
    if base == cand:
        st.warning("Pick two different runs.")
        return
    base_run, cand_run = ctx.index.run(base), ctx.index.run(cand)
    prov = pd.DataFrame([{"field": label, "baseline": _fmt(base_run.get(key)), "candidate": _fmt(cand_run.get(key))}
                         for key, label in PROVENANCE_FIELDS])
    with st.expander("Provenance of both runs", icon=":material/fingerprint:", expanded=False):
        st.dataframe(prov, hide_index=True, width="stretch")
        st.caption("Stage-code fingerprints come from the artifacts' stage manifests — they identify the code that "
                   "produced each run. The dashboard's own git SHA is only the indexer's.")
    with st.expander("Config and calibration changes", icon=":material/tune:"):
        changes, unavailable = config_diff(base_run, cand_run)
        for message in unavailable:
            st.info(message)
        if not changes.empty:
            table(changes, key="rc_config_diff", name="config_calibration_diff", run_key=cand, height=320)
        elif not unavailable:
            st.caption("No config or calibration values changed.")
        st.caption("Values are read from config bytes verified against each artifact fingerprint; this is not proof of a per-product cause.")
    causes = run_level_causes(base_run, cand_run)
    if causes:
        st.caption("Run-level causes: " + ", ".join(causes))
    if base_run.get("plane") != cand_run.get("plane"):
        st.caption("Totals compare on the shipped whole-number basis because one side is a catalog.")
    if "pillar_totals_only" in (base_run.get("fidelity"), cand_run.get("fidelity")):
        st.info("One side is a pillar-totals-only catalog: movements show deltas, not causes.", icon=":material/info:")

    deltas = ctx.deltas(base, cand)
    summary = summarize(deltas)
    kpis([("Moved", f"{summary.get('moved', 0):,}", None), ("Tier crossed", f"{summary.get('tier_crossed', 0):,}", None),
          ("Status changed", f"{summary.get('status_changed', 0):,}", None),
          ("Safety changed", f"{summary.get('safety_changed', 0):,}", "Always review"),
          ("Added / removed", f"{summary.get('added', 0):,} / {summary.get('removed', 0):,}", None),
          ("Unexplained", f"{summary.get('unexplained', 0):,}", "No pillar or run-level cause")])

    tab_movers, tab_causes, tab_dist, tab_trends = st.tabs(["Movers", "By cause", "Distribution", "Trends"])
    with tab_movers:
        row = st.columns(5)
        only = row[0].multiselect("Show", ["moved", "tier crossed", "status changed", "safety changed", "unexplained",
                                           "added", "removed"], default=["moved"], key="rc_only")
        min_delta = row[1].number_input("|Δ| ≥", 0.0, 100.0, 0.0, 0.5, key="rc_min")
        pillar = row[2].selectbox("Changed pillar", ["any", *PILLARS], format_func=lambda p: PILLAR_LABELS.get(p, p), key="rc_pillar")
        view = deltas.copy()
        mask = pd.Series(False, index=view.index)
        flags = {"moved": view["moved"].astype(bool), "tier crossed": view["tier_crossed"].astype(bool),
                 "status changed": view["status_changed"].astype(bool), "safety changed": view["safety_changed"].astype(bool),
                 "unexplained": ~view["explained"].astype(bool), "added": view["presence"] == "added",
                 "removed": view["presence"] == "removed"}
        for flag in only or list(flags):
            mask |= flags[flag].fillna(False)
        view = view[mask]
        if min_delta:
            view = view[view["delta"].abs() >= min_delta]
        if pillar != "any":
            view = view[view["changed_pillars"].map(lambda c: pillar in list(c))]
        columns = ["dsld_id", "product_name", "brand_name", "total_before", "total_after", "delta", "tier_before",
                   "tier_after", "product_safety_status_before", "product_safety_status_after", "changed_pillars",
                   "reason_codes", "run_causes", "safety_causes", "entries_added", "entries_removed", "pillar_attributed",
                   "explained", "delta_basis"]
        ordered = view.reindex(view["delta"].abs().sort_values(ascending=False).index)[columns].reset_index(drop=True)
        picked = table(ordered, key="rc_movers", name="movers", run_key=cand, select=True, height=460,
                       caption="Select a row to open the product trace.",
                       column_config={"delta": st.column_config.NumberColumn("Δ", format="%+.1f")})
        if picked:
            selected = ordered.iloc[picked[0]]
            target = base if deltas.set_index("dsld_id").loc[selected["dsld_id"], "presence"] == "removed" else cand
            shell.go("product-trace", trace_dsld_id=str(selected["dsld_id"]),
                     plane=ctx.index.run(target)["plane"], run=target)
    with tab_causes:
        counter: Counter = Counter()
        sums: Counter = Counter()
        for codes in deltas["reason_codes"].dropna():
            for code in json.loads(codes):
                for cause in code.get("causes") or []:
                    key = (code["pillar"], cause)
                    counter[key] += 1
                    sums[key] += float(code.get("delta") or 0)
        rows = [{"pillar": PILLAR_LABELS.get(p, p), "cause": c, "products": n, "mean Δ": round(sums[(p, c)] / n, 2)}
                for (p, c), n in counter.most_common()]
        table(pd.DataFrame(rows), key="rc_causes", name="movement_causes", run_key=cand, height=420,
              caption="Pillar causes from replay.reason_codes (component, penalty, reference or formula changes).")
    with tab_dist:
        both = deltas[deltas["presence"] == "both"]
        fig = go.Figure(go.Histogram(x=both["delta"], nbinsx=60, marker={"color": TOKENS["accent"]},
                                     hovertemplate="Δ %{x}: %{y:,} products<extra></extra>"))
        fig.update_layout(height=280, title={"text": "Score change distribution", "font": {"size": 14}},
                          xaxis={"title": "Δ score"}, yaxis={"title": "products"})
        st.plotly_chart(fig, width="stretch", key="rc_hist")
        pillar_rows = [{"pillar": PILLAR_LABELS[p], "mean Δ": round(both[f"delta_{p}"].mean(), 3),
                        "products moved": int((both[f"delta_{p}"].abs() >= MOVE_EPS).sum())} for p in PILLARS]
        st.dataframe(pd.DataFrame(pillar_rows), hide_index=True, width="stretch")
    with tab_trends:
        _trends(ctx)


def _fmt(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or "—"
    return "—" if value in (None, "") else str(value)


def _trends(ctx: shell.PageContext) -> None:
    rows = []
    for run in ctx.index.runs():
        products = ctx.frame("products", run["run_key"], ["quality_score_status", "total", "tier",
                                                          *[f"pillar_{p}" for p in PILLARS]])
        scored = products[products["quality_score_status"] == "scored"] if "quality_score_status" in products else products
        totals = scored["total"].dropna()
        rows.append({"run_time": run.get("run_time"), "plane": run["plane"], "fidelity": run["fidelity"],
                     "config": ", ".join(v for v in run.get("config_versions") or [] if v), "products": len(products),
                     "p10": totals.quantile(0.1) if not totals.empty else None, "median": totals.median() if not totals.empty else None,
                     "p90": totals.quantile(0.9) if not totals.empty else None,
                     **{f"mean_{p}": scored[f"pillar_{p}"].mean() for p in PILLARS}})
    frame = pd.DataFrame(rows)
    frame["when"] = pd.to_datetime(frame["run_time"], utc=True, errors="coerce")
    frame = frame.sort_values("when")
    fig = go.Figure()
    fig.add_scatter(x=frame["when"], y=frame["p90"], mode="lines", line={"width": 0}, showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=frame["when"], y=frame["p10"], mode="lines", line={"width": 0}, fill="tonexty",
                    fillcolor="rgba(24,59,63,0.12)", name="p10–p90")
    fig.add_scatter(x=frame["when"], y=frame["median"], mode="lines+markers", name="median", line={"width": 2, "color": TOKENS["accent"]},
                    marker={"size": 8}, text=frame["plane"] + " · " + frame["config"], hovertemplate="%{text}<br>median %{y:.1f}<extra></extra>")
    fig.update_layout(height=300, title={"text": "Scored products — median and p10–p90 by run", "font": {"size": 14}},
                      yaxis={"title": "score", "range": [0, 100]})
    st.plotly_chart(fig, width="stretch", key="rc_trend")
    fig = go.Figure()
    for p in PILLARS:
        fig.add_scatter(x=frame["when"], y=frame[f"mean_{p}"], mode="lines+markers", name=PILLAR_LABELS[p],
                        line={"width": 2, "color": PILLAR_COLORS[p]}, marker={"size": 8})
    fig.update_layout(height=300, title={"text": "Pillar means by run", "font": {"size": 14}}, yaxis={"title": "points"})
    st.plotly_chart(fig, width="stretch", key="rc_pillar_trend")
    table(frame.drop(columns=["when"]), key="rc_trend_table", name="run_history", run_key=ctx.run_key, height=260,
          caption="Pillar-totals-only runs are older catalogs; every run is labelled with its fidelity.")
