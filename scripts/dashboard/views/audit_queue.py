"""Audit Queue: versioned findings, grouped by root cause, with local triage."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from scripts.dashboard import shell, triage
from scripts.dashboard.components.ui import kpis, table
from scripts.dashboard.findings_rules import RULES, SEVERITY_ORDER

CLOSED = {"Expected", "Resolved", "Accepted exception", triage.RESOLVED_BY_RUN}


def render(ctx: shell.PageContext) -> None:
    if not shell.banner(ctx):
        return
    findings = ctx.findings()
    if findings.empty:
        st.success("No findings in the latest candidate and release runs.", icon=":material/check_circle:")
        _rules_reference()
        return
    findings["triage_status"] = findings.get("triage_status", pd.Series("Open", index=findings.index)).fillna("Open")
    open_ = findings[~findings["triage_status"].isin(CLOSED)]
    kpis([(severity.title(), f"{int((open_['severity'] == severity).sum()):,}", f"Open {severity} findings")
          for severity in SEVERITY_ORDER] + [("Closed", f"{len(findings) - len(open_):,}", "Expected, resolved or accepted")])

    row = st.columns(5)
    severity = row[0].multiselect("Severity", SEVERITY_ORDER, default=["critical", "high"], key="aq_sev")
    plane = row[1].multiselect("Plane", sorted(findings["plane"].dropna().unique()), key="aq_plane")
    category = row[2].multiselect("Category", sorted(findings["category"].dropna().unique()), key="aq_cat")
    status = row[3].multiselect("Triage", ["Open", *triage.STATUSES[1:], triage.RESOLVED_BY_RUN], default=["Open", "Investigating"],
                                key="aq_status")
    search = row[4].text_input("Search", placeholder="rule, product, brand", key="aq_search")
    view = findings
    if severity:
        view = view[view["severity"].isin(severity)]
    if plane:
        view = view[view["plane"].isin(plane)]
    if category:
        view = view[view["category"].isin(category)]
    if status:
        view = view[view["triage_status"].isin(status)]
    if search:
        text = search.lower()
        hay = view[["rule_id", "message", "product_name", "brand_name", "dsld_id", "subject"]].astype(str).apply(
            lambda col: col.str.lower()).agg(" ".join, axis=1)
        view = view[hay.str.contains(text, regex=False)]

    st.markdown("#### By root cause")
    groups = (view.groupby(["severity", "rule_id", "rule_version", "message", "pillar", "plane"], dropna=False)
              .agg(products=("dsld_id", "nunique"), findings=("finding_id", "count"),
                   example=("current_value", "first"), first_seen=("first_seen", "min"), last_seen=("last_seen", "max"))
              .reset_index())
    groups["order"] = groups["severity"].map({s: i for i, s in enumerate(SEVERITY_ORDER)})
    groups = groups.sort_values(["order", "findings"], ascending=[True, False]).drop(columns="order")
    table(groups, key="aq_groups", name="findings_by_cause", run_key=ctx.run_key, height=280)

    st.markdown("#### Findings")
    columns = ["severity", "rule_id", "plane", "dsld_id", "product_name", "brand_name", "pillar", "subject",
               "current_value", "expected", "triage_status", "owner", "notes", "first_seen", "last_seen", "policy",
               "finding_id", "rule_version", "run_key", "config_fingerprint"]
    columns = [c for c in columns if c in view.columns]
    ordered = view.assign(order=view["severity"].map({s: i for i, s in enumerate(SEVERITY_ORDER)})) \
        .sort_values(["order", "rule_id"]).drop(columns="order")[columns].reset_index(drop=True)
    picked = table(ordered, key="aq_findings", name="findings", run_key=ctx.run_key, select=True, height=420,
                   caption="Select a finding to triage it or open the product.")
    if picked:
        _triage_panel(ctx, ordered.iloc[picked[0]], ordered)
    _rules_reference()


def _triage_panel(ctx: shell.PageContext, finding: pd.Series, visible: pd.DataFrame) -> None:
    with st.container(border=True):
        st.markdown(f"**{finding['rule_id']}** v{int(finding['rule_version'])} · {finding.get('product_name') or finding.get('subject') or ''}")
        st.caption(f"Value {finding.get('current_value')} · expected {finding.get('expected')} · policy {finding.get('policy')}")
        cols = st.columns(4)
        current = finding.get("triage_status") if finding.get("triage_status") in triage.STATUSES else "Open"
        status = cols[0].selectbox("Status", triage.STATUSES, index=triage.STATUSES.index(current), key=f"aq_t_status_{finding['finding_id']}")
        owner = cols[1].text_input("Owner", value=str(finding.get("owner") or ""), key=f"aq_t_owner_{finding['finding_id']}")
        stamp = finding.get("config_fingerprint")
        scope_options = ([stamp] if isinstance(stamp, str) and stamp else [] if pd.notna(finding.get("dsld_id"))
                         else (ctx.index.run(finding.get("run_key")) or {}).get("config_fingerprints") or [])
        scope = cols[2].selectbox("Config fingerprint scope (accepted exceptions)",
                                   scope_options or [""], key=f"aq_t_scope_{finding['finding_id']}",
                                   help="An accepted exception reopens under any other config fingerprint")
        review_by = cols[3].date_input("Review by", value=None, key=f"aq_t_review_{finding['finding_id']}", min_value=date.today())
        notes = st.text_area("Notes", value=str(finding.get("notes") or ""), key=f"aq_t_notes_{finding['finding_id']}")
        same = visible[(visible["rule_id"] == finding["rule_id"]) & (visible["rule_version"] == finding["rule_version"])]
        apply_all = st.checkbox(f"Apply to all {len(same)} visible findings of this rule", key=f"aq_t_bulk_{finding['finding_id']}")
        b1, b2 = st.columns([1, 1])
        if b1.button("Save triage", type="primary", icon=":material/save:"):
            if status == "Accepted exception" and not scope:
                st.error("A recorded config fingerprint is required for an accepted exception.")
                return
            targets = same if apply_all else visible[visible["finding_id"] == finding["finding_id"]]
            for item in targets.itertuples():
                triage.set_status(item.finding_id, item.rule_id, int(item.rule_version), status, owner=owner or None,
                                  notes=notes or None, config_scope=scope if scope and status == "Accepted exception" else None,
                                  review_by=review_by.isoformat() if review_by else None)
            st.toast(f"Saved {len(targets)} finding(s) as {status}")
            st.rerun()
        if finding.get("dsld_id") and not pd.isna(finding.get("dsld_id")):
            if b2.button("Open product trace", icon=":material/receipt_long:"):
                shell.go("product-trace", trace_dsld_id=str(finding["dsld_id"]),
                         plane=finding["plane"], run=finding["run_key"])


def _rules_reference() -> None:
    with st.expander("Rule catalog", icon=":material/rule:"):
        st.dataframe(pd.DataFrame([{"rule": r.rule_id, "version": r.version, "severity": r.severity,
                                    "category": r.category, "finding": r.message, "expected": r.expected,
                                    "policy": r.policy} for r in RULES]), hide_index=True, width="stretch")
