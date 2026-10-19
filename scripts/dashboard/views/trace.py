"""Product Trace: every point of one product's score, from the scorer's own receipts."""

from __future__ import annotations

import json
from html import escape

import pandas as pd
import plotly.graph_objects as go
import pyarrow.dataset as pds
import streamlit as st

from scripts.dashboard import shell
from scripts.dashboard.components.theme import PILLAR_COLORS, SEVERITY, TOKENS
from scripts.dashboard.components.ui import (
    chip, chips, human, kind_label, kpis, muted, pillar_bars, pillar_state, receipt_label, severity_tone, table,
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


def _pts(value: float) -> str:
    return f"{value:+.2f}".replace("-", "−")


def _receipt_detail(entry_id: str, row: dict, additives: pd.DataFrame) -> str | None:
    """Which label fact a line came from, when the index recorded it."""
    if entry_id == "dose_safety_ceiling" and row.get("dose_cap_nutrient"):
        pct = row.get("dose_cap_pct_ul")
        return f"{row['dose_cap_nutrient']} is at {pct:.0f}% of its daily upper limit" if pd.notna(pct) else str(row["dose_cap_nutrient"])
    if entry_id == "additive_or_sweetener_penalty" and not additives.empty:
        return " · ".join(f"{', '.join(map(str, list(a.labels)[:3])) if a.labels is not None and len(a.labels) else a.rule_id} "
                          f"−{float(a.penalty or 0):g} ({a.tier} concern)" for a in additives.itertuples())
    return None


def _receipt(product: dict, pillar: str, row: dict) -> None:
    """One pillar as a plain receipt: every line that moved points, then the pillar total."""
    ledgers = product["ledgers"]
    found = ledgers[ledgers["pillar"] == pillar]
    if found.empty:
        st.info(f"No {PILLAR_LABELS[pillar]} receipt: the product has no scored pillars (suppressed or not scored).")
        return
    ledger = found.iloc[0].to_dict()
    receipts = product["receipts"][product["receipts"]["pillar"] == pillar].sort_values("seq")
    score, mx = float(ledger.get("score") or 0), float(ledger.get("max") or 0)
    html = [f'<div class="pg-card" style="margin-bottom:0.8rem"><div class="pg-card-head">'
            f'<span class="pg-dot" style="background:{PILLAR_COLORS[pillar]}"></span>{escape(PILLAR_LABELS[pillar])}'
            f'<span class="pg-card-score">{score:.1f} / {mx:g}</span></div>']
    why = _clean(ledger.get("reason")) or pillar_state(pillar, row)
    if why:
        html.append(f'<div class="pg-why">{escape(str(why))}</div>')
    shown = 0
    for r in receipts.itertuples():
        value = float(r.points or 0)
        if r.kind == "rounding" and abs(value) < 0.005:
            continue  # sub-hundredth residue of rounding to one decimal; kept in the technical table
        detail = _receipt_detail(str(r.entry_id), row, product["additives"])
        tone = {"deduction": "critical", "cap": "high", "floor": "ok"}.get(str(r.kind), "")
        html.append(
            f'<div class="pg-line"><span class="pg-pts">{_pts(value)}</span>'
            f'<span>{escape(receipt_label(r.entry_id))}'
            + (f'<span class="pg-detail">{escape(detail)}</span>' if detail else "")
            + f'<span class="pg-id">{escape(str(r.source or r.entry_id))}</span></span>'
            f'{chip(kind_label(str(r.kind)), tone)}</div>')
        shown += 1
    if not shown:
        html.append('<div class="pg-line"><span></span><span>No receipt lines recorded for this pillar.</span><span></span></div>')
    left = mx - score
    html.append(f'<div class="pg-total"><span class="pg-pts">= {score:.1f}</span><span>out of {mx:g}</span>'
                f'<span style="color:{TOKENS["muted"]};font-weight:400">'
                f'{"full marks" if left < 0.05 else f"{left:.1f} below max"}</span></div>')
    nominal, realized = float(ledger.get("nominal_deductions") or 0), float(ledger.get("realized_deductions") or 0)
    if realized - nominal > 0.005:
        html.append(f'<div class="pg-detail" style="margin-top:0.4rem">Deductions listed {_pts(nominal)}, actually taken '
                    f'{_pts(realized)}: the rest would have pushed the pillar below its minimum.</div>')
    elif nominal - realized > 0.005:
        html.append(f'<div class="pg-detail" style="margin-top:0.4rem;color:{SEVERITY["critical"][0]}">Deductions listed '
                    f'{_pts(nominal)} but {_pts(realized)} taken — more than listed; see the Audit Queue.</div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)
    if ledger.get("entry_sum") is not None and abs(float(ledger["entry_sum"]) - score) > 0.0505:
        st.error(f"Receipt sums to {ledger['entry_sum']} but the pillar is {score} — see the Audit Queue.")


def _clean(value) -> str:
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)


def _amount(value, unit) -> str:
    return "" if value is None or pd.isna(value) else f"{float(value):,.4g} {_clean(unit)}".strip()


def _label_facts(ctx: shell.PageContext, dsld_id: str, dose_refs: pd.DataFrame, dose_flags: pd.DataFrame) -> None:
    """The printed label next to the score, with each nutrient's share of its daily upper limit."""
    status = ctx.index.ingredient_staleness()
    if not status["built"]:
        st.info("Supplement Facts come from the ingredient index, which is not built yet.")
        st.code("python -m scripts.dashboard.score_index refresh --ingredients", language="bash")
        return
    match = pds.field("dsld_id") == dsld_id
    facts = ctx.index.ingredient_frame("label_facts", filter=match)
    meta = ctx.index.ingredient_frame("product_meta", filter=match)
    if facts.empty and meta.empty:
        st.info("This product has no label rows in the ingredient index (rebuild it with `refresh --ingredients`).")
        return
    info = {key: _clean(value) for key, value in (meta.iloc[0].to_dict() if not meta.empty else {}).items()}
    meta_bits = [b for b in (info.get("serving") and f"Serving: {info['serving']}",
                             info.get("servings_per_container") and f"{float(info['servings_per_container']):g} servings per container",
                             info.get("form_factor")) if b]
    refs = {str(ref.canonical_id): ref for ref in dose_refs.itertuples()}
    part = info.get("source_part")
    scored_part = ((ctx.run or {}).get("parts") or {}).get(part) or {}
    enriched_part = (ctx.index.meta.get("ingredient_parts") or {}).get(part) or {}
    same_source = all(scored_part.get(key) and scored_part[key] == enriched_part.get(key)
                      for key in ("run_id", "reference_data"))
    current_units_match = (ctx.plane == "candidate" and ctx.run_key == ctx.index.latest("candidate")
                           and same_source and not status["stale"] and not ctx.index.staleness()["stale"])
    over = {}  # the scorer records % of UL only for nutrients its dose-safety check flagged
    recorded_limits = {}
    for flag in dose_flags.itertuples():
        if pd.notna(flag.pct_ul) and flag.nutrient:
            over[str(flag.nutrient).lower()] = max(float(flag.pct_ul), over.get(str(flag.nutrient).lower(), 0.0))
            if pd.notna(flag.ul) and _clean(flag.ul_unit):
                recorded_limits[str(flag.nutrient).lower()] = flag
    rows = ['<div class="pg-card"><div class="pg-facts-head">Supplement Facts</div>',
            f'<div class="pg-facts-meta">{escape(" · ".join(map(str, meta_bits)))}</div>',
            '<div class="pg-label-wrap"><table class="pg-label"><tr><th>Ingredient</th><th class="r">Per serving</th><th class="r">% DV</th>'
            '<th class="r" title="Highest directed daily amount, as the scorer computed it">Per day</th>'
            '<th class="r" title="Tolerable upper intake level used by the scorer; the percentage is recorded by the '
            'dose-safety check when a nutrient crosses it">Upper limit</th></tr>']
    actives = facts[facts["section"] == "active"].sort_values("seq")
    for f in actives.itertuples():
        ref = refs.get(str(f.canonical_id)) if int(f.depth or 0) == 0 else None
        pct = over.get(str(f.name or "").lower())
        if pct is None and ref is not None:
            pct = over.get(str(ref.nutrient).lower())
        per_day = _amount(ref.per_day_max, ref.unit) if ref is not None else ""
        bound = recorded_limits.get(str(ref.nutrient if ref is not None else f.name).lower())
        reference_unit = _clean(getattr(f, "nutrient_unit", None)) if current_units_match else ""
        if bound is not None:
            limit, pct = _amount(bound.ul, bound.ul_unit), float(bound.pct_ul)
        elif ref is not None and reference_unit:
            limit = _amount(ref.ul, reference_unit)
        else:
            limit, pct = "", None
        indent = f'padding-left:{0.4 + 1.1 * int(f.depth or 0):.1f}rem'
        rows.append(
            f'<tr><td style="{indent}">{escape(_clean(f.name) or "—")}'
            + (f'<span class="form">{escape(_clean(f.form))}</span>' if _clean(f.form) else "")
            + f'</td><td class="num">{escape(_clean(f.amount) or "—")}</td>'
            f'<td class="num">{"" if pd.isna(f.daily_value) else f"{f.daily_value:g}%"}</td>'
            f'<td class="num">{escape(per_day)}</td>'
            f'<td class="num{" over" if pct is not None and pct > 100 else ""}">{escape(limit)}'
            f'{"" if pct is None else f" · {pct:.0f}%"}</td></tr>')
    rows.append("</table></div>")
    inactive = facts[facts["section"] == "inactive"].sort_values("seq")["name"].dropna().tolist()
    if inactive:
        rows.append(f'<div class="pg-facts-meta" style="margin-top:0.6rem"><b>Other ingredients:</b> {escape(", ".join(inactive))}</div>')
    if info.get("directions"):
        rows.append(f'<div class="pg-facts-meta"><b>Directions:</b> {escape(str(info["directions"]))}</div>')
    rows.append("</div>")
    st.markdown("".join(rows), unsafe_allow_html=True)
    stale = " — stale, may predate this run" if status["stale"] else ""
    muted(f"Label as recorded in the enriched data (ingredient index built {status.get('built_at') or '—'}{stale}). "
          "Per day and upper limit come from the scorer's dose references. A red upper limit with a percentage is a "
          "nutrient the dose-safety check found over its limit. Reference units come from the matching current "
          "enriched record or a recorded ceiling; a limit without a bound unit is left unavailable, not inferred from the dose unit.")


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

    st.markdown("#### How the score adds up")
    pillar_bars(row, ctx.maxima)
    parts = [(PILLAR_LABELS[p], row.get(f"pillar_{p}")) for p in PILLARS]
    if pd.notna(row.get("total")) and all(v is not None and pd.notna(v) for _, v in parts):
        equation = " + ".join(f"<b>{float(v):.1f}</b> {escape(name)}" for name, v in parts)
        st.markdown(f'<div class="pg-sum">{equation} = <b>{row["total"]:.1f} / 100</b></div>', unsafe_allow_html=True)

    left, right = st.columns([5, 6])
    with left:
        st.markdown("#### Why each pillar scored what it did")
        for pillar in PILLARS:
            _receipt(product, pillar, row)
        muted("Each line is a receipt entry recorded by the scorer; the grey text is its source in the scoring config. "
              + NO_LINK)
    with right:
        st.markdown("#### Label as printed")
        _label_facts(ctx, dsld_id, product["dose_refs"], product["dose_flags"])

    missing = list(row.get("completeness_missing") if row.get("completeness_missing") is not None else [])
    signals = list(row.get("safety_signals") if row.get("safety_signals") is not None else [])
    if missing or signals or pd.notna(row.get("completeness_score_cap")):
        st.caption(f"Completeness gate — missing: {', '.join(missing) or 'none'} · score cap: "
                   f"{row.get('completeness_score_cap') if pd.notna(row.get('completeness_score_cap')) else 'none'} · "
                   f"safety signals: {', '.join(signals) or 'none'}")

    with st.expander("Technical details — raw receipt, dose checks and additive rules", icon=":material/table:"):
        receipts = product["receipts"].sort_values(["pillar", "seq"]).assign(
            pillar=lambda d: d["pillar"].map(PILLAR_LABELS), line=lambda d: d["entry_id"].map(receipt_label),
            type=lambda d: d["kind"].map(kind_label))
        table(receipts[["pillar", "line", "entry_id", "type", "points", "raw", "source", "basis", "withheld_by"]],
              key="trace_receipts", name=f"receipt_{dsld_id}", run_key=ctx.run_key, height=320,
              caption="Every receipt entry, unrounded. Points sum to each pillar.")
        ledgers = product["ledgers"].assign(pillar=lambda d: d["pillar"].map(PILLAR_LABELS))
        table(ledgers[["pillar", "score", "max", "nominal_deductions", "realized_deductions", "unawarded", "state"]],
              key="trace_ledgers", name=f"ledgers_{dsld_id}", run_key=ctx.run_key, height=260,
              caption="unawarded = capacity minus the score the pillar would have without deductions (caps included).")
        flags = product["dose_flags"]
        table(flags[["state", "nutrient", "pct_ul", "pct_ul_at_minimum", "is_ceiling", "ceiling_kind", "ul", "ul_unit",
                     "reason"]] if not flags.empty else flags, key="trace_flags", name=f"dose_flags_{dsld_id}",
              run_key=ctx.run_key, height=220, caption="Dose safety checks: % of the upper limit at the highest and lowest directed use.")
        table(product["dose_refs"].drop(columns=["dsld_id"]), key="trace_refs", name=f"dose_refs_{dsld_id}",
              run_key=ctx.run_key, height=260, caption="Dose references per nutrient (% of RDA/AI and of the upper limit).")
        table(product["additives"].drop(columns=["dsld_id"]), key="trace_additives", name=f"additives_{dsld_id}",
              run_key=ctx.run_key, height=220, caption="Additive and sweetener rules that deducted Formula checks points.")

    st.markdown("#### Ingredient matches and peer context")
    ingredient_status = ctx.index.ingredient_staleness()
    if ingredient_status["built"]:
        if ingredient_status["stale"]:
            st.warning("Ingredient index is stale; ingredient details may predate this run.")
        st.caption(f"How each label row matched the ingredient database (enriched index built at "
                   f"{ingredient_status.get('built_at')}; not a snapshot of this selected scoring run).")
        ingredients = ctx.index.ingredient_frame(filter=pds.field("dsld_id") == dsld_id)
        table(ingredients[ingredients["dsld_id"] == dsld_id], key="trace_ingredients",
              name=f"ingredients_{dsld_id}",
              run_key=f"ingredient-index-{ingredient_status.get('built_at')}", height=280)
    else:
        st.info("Ingredient index unavailable. Build it with `python -m scripts.dashboard.score_index refresh --ingredients`.")
    from scripts.dashboard.views.score_lab import peer_percentiles
    peers = peer_percentiles(ctx.products())
    peer = peers[peers["dsld_id"] == dsld_id]
    if peer.empty:
        st.caption("Peer percentile unavailable: requires a complete scored product and at least 30 category peers under the same config.")
    else:
        value = peer.iloc[0]
        st.caption(f"Category peer percentile: {value['peer_percentile']:.1f} among {int(value['peer_n']):,} complete scored products "
                   "in this run and config. Context only; never a quality score.")

    findings = ctx.index.findings()
    mine = findings[(findings["dsld_id"] == dsld_id) & (findings["run_key"] == ctx.run_key)] if not findings.empty else findings
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
