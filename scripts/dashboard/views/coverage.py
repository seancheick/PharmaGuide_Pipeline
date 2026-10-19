"""Coverage & Calibration: calibration records, assessment coverage, and the golden set."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts.dashboard import shell
from scripts.dashboard.components.theme import TOKENS
from scripts.dashboard.components.ui import DOSE_BASIS_LABELS, EVIDENCE_STATE_LABELS, human, kpis, table
from scripts.dashboard.findings_rules import CALIBRATION_STALE_DAYS, calibration_records, canaries, owner_symbol_exists

UNRATED = {"A1_unrated_neutral", "panel_form_quality_unrated_neutral"}


def calibration_frame() -> pd.DataFrame:
    rows = []
    today = date.today()
    for record in calibration_records():
        try:
            age = (today - date.fromisoformat(str(record.get("review_date"))[:10])).days
        except ValueError:
            age = None
        rows.append({
            "record": record["path"], "purpose": record.get("purpose"), "population": record.get("population"),
            "reference_type": record.get("reference_type"), "curve": record.get("curve"),
            "approval_status": record.get("approval_status"),
            "approved": str(record.get("approval_status") or "").startswith("approved"),
            "sources": len(record.get("source_ids") or []), "owner": record.get("owner"),
            "owner_found": owner_symbol_exists(str(record.get("owner") or "")),
            "rationale": record.get("rationale"), "review_date": record.get("review_date"), "review_age_days": age,
            "stale": age is not None and age > CALIBRATION_STALE_DAYS,
        })
    return pd.DataFrame(rows)


def _bar(counts: pd.Series, title: str, key: str, labels: dict | None = None) -> None:
    counts = counts.sort_values()
    fig = go.Figure(go.Bar(x=counts.values, y=[(labels or {}).get(i, human(i)) for i in counts.index], orientation="h",
                           marker={"color": TOKENS["accent"], "cornerradius": 4}, text=[f"{v:,}" for v in counts.values],
                           textposition="outside", hovertemplate="%{y}: %{x:,}<extra></extra>"))
    fig.update_layout(height=max(220, 28 * len(counts) + 60), title={"text": title, "font": {"size": 14}},
                      xaxis={"title": "products"})
    st.plotly_chart(fig, width="stretch", key=key)


def render(ctx: shell.PageContext) -> None:
    if not shell.banner(ctx):
        return
    products = ctx.products()
    tab_cal, tab_cov, tab_gold = st.tabs(["Calibration records", "Coverage", "Golden set"])

    with tab_cal:
        frame = calibration_frame()
        kpis([("Records", f"{len(frame):,}", "Config-owned numeric anchors in quality_score.json"),
              ("Not approved", f"{int((~frame['approved']).sum()):,}", None),
              ("Without sources", f"{int((frame['sources'] == 0).sum()):,}", None),
              ("Owner not found", f"{int((~frame['owner_found']).sum()):,}", "owner path::symbol missing from code"),
              ("Stale (> 1 year)", f"{int(frame['stale'].sum()):,}", None)])
        table(frame, key="cov_cal", name="calibration_records", run_key=ctx.run_key, height=460,
              caption="Product artifacts do not name these records, so the dashboard never links a product to one by "
                      "inference: calibration reference linkage is unavailable in this artifact.")

    with tab_cov:
        scored = products[products["quality_score_status"] == "scored"]
        kpis([("Unmapped actives", f"{int((products['unmapped_actives_total'] > 0).sum()):,}", "Products with ≥1 unmapped active"),
              ("Unrated forms", f"{int(products['receipt_entry_ids'].map(lambda v: bool(UNRATED & set(v))).sum()):,}", None),
              ("Dose neutral", f"{int(scored['neutral_only_pillars'].map(lambda v: 'dose' in list(v)).sum()):,}", None),
              ("Evidence not assessed", f"{int((scored['evidence_display_state'].fillna('assessed') != 'assessed').sum()):,}", None),
              ("Fallbacks used", f"{int((products['fallbacks_used'] > 0).sum()):,}", None)])
        c1, c2 = st.columns(2)
        with c1:
            _bar(scored["evidence_state"].fillna("none").value_counts(), "Evidence state", "cov_ev", EVIDENCE_STATE_LABELS)
            _bar(scored["verification_tier"].fillna("none").value_counts(), "Verification tier", "cov_ver")
        with c2:
            _bar(scored["dose_basis"].fillna("benchmarked / earned").value_counts(), "Dose basis", "cov_dose", DOSE_BASIS_LABELS)
            _bar(products["module"].fillna("none").value_counts(), "Route", "cov_route")
        unmapped = products[products["unmapped_actives_total"] > 0].groupby("brand_name").agg(
            products=("dsld_id", "count"), unmapped_actives=("unmapped_actives_total", "sum")).reset_index()
        table(unmapped.sort_values("unmapped_actives", ascending=False), key="cov_unmapped", name="unmapped_by_brand",
              run_key=ctx.run_key, height=300, caption="Unmapped actives by brand (details in Data Quality → Unmapped).")

    with tab_gold:
        golden = pd.DataFrame(canaries())
        if golden.empty:
            st.info("No golden set found at scripts/data/canary_products.json.")
            return
        golden["dsld_id"] = golden["dsld_id"].astype(str)
        current = products.set_index("dsld_id")
        deltas = ctx.deltas(ctx.baseline_key(), ctx.run_key)
        moved = deltas.set_index("dsld_id")["delta"] if not deltas.empty else pd.Series(dtype=float)
        findings = ctx.index.findings()
        flagged = set(findings[findings["run_key"] == ctx.run_key]["dsld_id"].dropna()) if not findings.empty else set()
        rows = []
        for canary in golden.to_dict("records"):
            pid = canary["dsld_id"]
            hit = current.loc[pid] if pid in current.index else None
            rows.append({
                "dsld_id": pid, "product": canary.get("product_name"), "brand": canary.get("brand_name"),
                "class": canary.get("primary_class"), "present": hit is not None,
                "score": None if hit is None else hit["total"], "tier": None if hit is None else hit["tier"],
                "route": None if hit is None else hit["module"], "status": None if hit is None else hit["quality_score_status"],
                "safety": None if hit is None else hit["product_safety_status"],
                "Δ vs baseline": moved.get(pid), "findings": pid in flagged,
                "expected_dose_route_v4 (historical label)": canary.get("expected_dose_route_v4"),
            })
        frame = pd.DataFrame(rows)
        kpis([("Canaries", f"{len(frame):,}", None), ("Missing", f"{int((~frame['present']).sum()):,}", None),
              ("Moved vs baseline", f"{int(pd.to_numeric(frame['Δ vs baseline'], errors='coerce').abs().fillna(0).ge(0.05).sum()):,}", None),
              ("With findings", f"{int(frame['findings'].sum()):,}", None)])
        st.caption("Behavioural v4 expectations (tier band, route, assessment and safety status, pillar invariants) are "
                   "added by the golden-set data batch and checked here once present. expected_dose_route_v4 predates "
                   "today's route vocabulary, so it is shown, not compared.")
        picked = table(frame, key="cov_gold", name="golden_set", run_key=ctx.run_key, select=True, height=480)
        if picked:
            shell.go("product-trace", trace_dsld_id=str(frame.iloc[picked[0]]["dsld_id"]))
