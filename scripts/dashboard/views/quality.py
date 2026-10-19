from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts.dashboard.components.data_table import data_table
from scripts.dashboard.components.metric_cards import metric_row




def render_quality(data):
    """Pipeline data-quality panels (release label trust, coverage, unmapped, forms, fallbacks, config)."""
    dataset_scope = st.session_state.get("dataset_filter", "All Datasets")
    _render_label_trust_quality(data)
    st.divider()
    _render_coverage_gate(data, dataset_scope)
    st.divider()
    try:
        tabs = st.tabs(["Unmapped Hotspots", "Form Curation", "Fallback & Review Queues", "Config Snapshot"])
        if not isinstance(tabs, (list, tuple)) or len(tabs) < 4:
            raise ValueError("tabs unavailable")
        tab_unmapped, tab_forms, tab_fallbacks, tab_config = tabs[:4]
    except Exception:
        tab_unmapped = tab_forms = tab_fallbacks = tab_config = st
    with tab_unmapped:
        _render_unmapped_hotspots(data, dataset_scope)
    with tab_forms:
        _render_form_curation(data, dataset_scope)
    with tab_fallbacks:
        _render_fallback_tables(data, dataset_scope)
    with tab_config:
        _render_config_snapshot(data)


def _count_rows(values: dict, *, label: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {label: name.replace("_", " ").title(), "count": count}
            for name, count in sorted(values.items())
        ]
    )


def _render_label_trust_quality(data):
    st.write("### Label Fidelity & Trust QA")
    st.caption(
        "Only aggregate release diagnostics are rendered. Private report photos, "
        "user identifiers, free text, and health data are never displayed."
    )
    metrics = data.label_trust or {}
    if not isinstance(metrics, dict):
        metrics = {}

    total_products = int(metrics.get("total_products") or 0)
    history_coverage = metrics.get("formula_history_coverage_pct")
    average_completeness = metrics.get("average_completeness_pct")
    metric_row([
        ("Products audited", total_products),
        ("Supported ledger", int(metrics.get("supported_products") or 0)),
        ("Unsupported ledger", int(metrics.get("unsupported_products") or 0)),
        ("Complete labels", int(metrics.get("complete_products") or 0)),
        ("Incomplete labels", int(metrics.get("incomplete_products") or 0)),
        (
            "Completeness unavailable",
            int(metrics.get("unavailable_products") or 0),
        ),
        ("Invalid audit contract", int(metrics.get("invalid_audit_products") or 0)),
    ])
    metric_row([
        (
            "Average completeness",
            f"{average_completeness:.1f}%"
            if average_completeness is not None
            else "N/A",
        ),
        ("Displayed label rows", int(metrics.get("total_display_rows") or 0)),
        (
            "Ingredient identity failures",
            int(metrics.get("integrity_failures") or 0),
        ),
        (
            "Products with identity failures",
            int(metrics.get("identity_failure_products") or 0),
        ),
        (
            "Formula history coverage",
            f"{history_coverage:.1f}%" if history_coverage is not None else "N/A",
        ),
    ])
    if total_products == 0:
        st.info(
            "No label-ledger detail blobs are available. Counts are zero and "
            "percentage metrics remain unavailable rather than implying 0% quality."
        )

    state_groups = [
        ("Display disposition", metrics.get("display_dispositions") or {}),
        ("Form disclosure / assessment", metrics.get("form_states") or {}),
        ("Identity integrity", metrics.get("identity_states") or {}),
    ]
    try:
        columns = st.columns(3)
        if not isinstance(columns, (list, tuple)) or len(columns) < 3:
            raise ValueError("columns unavailable")
    except Exception:
        columns = [st, st, st]
    for column, (heading, values) in zip(columns, state_groups):
        with column:
            st.write(f"#### {heading}")
            if values:
                st.dataframe(
                    _count_rows(values, label="state"),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("No rows available.")

    rejected_signals = {
        "Unrecognized display dispositions": int(
            metrics.get("unrecognized_display_dispositions") or 0
        ),
        "Unrecognized form states": int(
            metrics.get("unrecognized_form_states") or 0
        ),
        "Unrecognized identity states": int(
            metrics.get("unrecognized_identity_states") or 0
        ),
        "Rejected mismatch outcomes": int(
            metrics.get("rejected_mismatch_outcomes") or 0
        ),
        "Rejected mismatch categories": int(
            metrics.get("rejected_mismatch_categories") or 0
        ),
        "Invalid mismatch summary": int(
            metrics.get("invalid_mismatch_summary") or 0
        ),
    }
    if any(rejected_signals.values()):
        st.warning(
            "Unrecognized or privacy-invalid aggregate rows were excluded. "
            "Investigate schema drift before treating the dashboard as clean."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {"signal": name, "count": count}
                    for name, count in rejected_signals.items()
                    if count
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    st.write("#### Completeness by product group")
    try:
        columns = st.columns(2)
        if not isinstance(columns, (list, tuple)) or len(columns) < 2:
            raise ValueError("columns unavailable")
    except Exception:
        columns = [st, st]
    for column, heading, rows in (
        (columns[0], "Brand", metrics.get("by_brand") or []),
        (columns[1], "Category", metrics.get("by_category") or []),
    ):
        with column:
            st.write(f"##### {heading}")
            if rows:
                data_table(pd.DataFrame(rows), max_rows=200, height=320)
            else:
                st.info(f"No {heading.lower()} breakdown available.")

    st.write("#### Label mismatch workflow")
    mismatch_outcomes = metrics.get("mismatch_outcomes") or {}
    mismatch_categories = metrics.get("mismatch_categories") or {}
    if not mismatch_outcomes and not mismatch_categories:
        if int(metrics.get("invalid_mismatch_summary") or 0):
            st.error(
                "The aggregate mismatch summary was rejected because its schema "
                "was invalid. Fix the export before using workflow metrics."
            )
        else:
            st.info(
                "No aggregate mismatch summary is loaded. Private reports and photos "
                "are intentionally not queried by this dashboard."
            )
        return
    try:
        columns = st.columns(2)
        if not isinstance(columns, (list, tuple)) or len(columns) < 2:
            raise ValueError("columns unavailable")
    except Exception:
        columns = [st, st]
    with columns[0]:
        st.write("##### Outcomes")
        if mismatch_outcomes:
            st.dataframe(
                _count_rows(mismatch_outcomes, label="status"),
                width="stretch",
                hide_index=True,
            )
    with columns[1]:
        st.write("##### Categories")
        if mismatch_categories:
            st.dataframe(
                _count_rows(mismatch_categories, label="category"),
                width="stretch",
                hide_index=True,
            )










def _render_coverage_gate(data, dataset_scope):
    st.write("### Coverage Gate")
    st.caption("Live dataset coverage from current output_* directories and report timestamps.")
    rows = []
    reports = _scoped_dataset_reports(data, dataset_scope)
    for dataset, report in reports.items():
        rows.append(
            {
                "dataset": dataset,
                "cleaned_count": report.get("cleaned_count", 0),
                "error_count": report.get("error_count", 0),
                "unmapped_active": len(report.get("unmapped_active", [])),
                "needs_review_active": len(report.get("needs_review_active", [])),
                "last_updated": report.get("latest_activity_at"),
            }
        )
    if not rows:
        st.info("No dataset output directories are available for coverage diagnostics.")
        return
    df = pd.DataFrame(rows)
    if not df.empty and "last_updated" in df.columns and df["last_updated"].notna().any():
        df["last_updated"] = pd.to_datetime(df["last_updated"]).dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M UTC")
    fig = go.Figure()
    for column in ["cleaned_count", "error_count", "unmapped_active", "needs_review_active"]:
        fig.add_trace(go.Bar(name=column.replace("_", " ").title(), x=df["dataset"], y=df[column]))
    fig.update_layout(barmode="group", height=320, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig, width="stretch")
    st.write("#### Coverage details")
    st.dataframe(df, width="stretch", height=260, hide_index=True)






def _render_unmapped_hotspots(data, dataset_scope):
    st.write("### Unmapped Hotspots")
    reports = _scoped_dataset_reports(data, dataset_scope)
    rows = []
    for dataset, report in reports.items():
        for row in report.get("unmapped_active", []):
            rows.append(
                {
                    "ingredient_name": row.get("ingredient_name") or row.get("name"),
                    "occurrences": row.get("occurrence_count") or row.get("count") or 1,
                    "dataset": dataset,
                }
            )
        for row in report.get("unmapped_inactive", []):
            rows.append(
                {
                    "ingredient_name": row.get("ingredient_name") or row.get("name"),
                    "occurrences": row.get("occurrence_count") or row.get("count") or 1,
                    "dataset": dataset,
                }
            )
    if not rows:
        st.info("No unmapped ingredient hotspots found in the discovered outputs.")
        return
    df = pd.DataFrame(rows).groupby("ingredient_name", as_index=False).agg(
        occurrences=("occurrences", "sum"),
        datasets=("dataset", lambda values: ", ".join(sorted(set(values)))),
    )
    df = df.sort_values(["occurrences", "ingredient_name"], ascending=[False, True])
    data_table(df, max_rows=50)


def _scoped(reports: dict, dataset_scope):
    if dataset_scope == "All Datasets":
        return reports
    return {dataset_scope: reports[dataset_scope]} if dataset_scope in reports else {}


def build_form_curation_rows(form_fallback_reports: dict) -> list[dict]:
    """One row per (parent, unmapped form token) across datasets, ranked by
    held products. Each row names a label form IQM does not recognize; the
    products carrying it are held until it is curated."""
    grouped: dict[tuple[str, str, str], dict] = {}
    for dataset, report in form_fallback_reports.items():
        for entry in (report or {}).get("form_fallbacks") or []:
            token = str(entry.get("unmapped_form_text") or "")
            gap_type = entry.get("gap_type") or "disclosed_form_unmapped"
            key = (gap_type, str(entry.get("canonical_id") or ""), token.lower().strip())
            row = grouped.setdefault(key, {
                "canonical_id": key[1], "parent_name": entry.get("parent_name") or "",
                "unmapped_form": token, "gap_type": gap_type,
                "occurrences": 0, "_products": set(), "_brands": set(), "_datasets": set(), "example": "",
            })
            row["occurrences"] += int(entry.get("occurrence_count") or 0)
            row["_products"].update(entry.get("dsld_ids") or [])
            row["_brands"].update(entry.get("brands") or [])
            row["_datasets"].add(dataset)
            examples = entry.get("examples") or []
            if not row["example"] and examples:
                first = examples[0]
                row["example"] = f"{first.get('dsld_id')}: {first.get('raw_source_text') or first.get('ingredient_label')}"
    rows = []
    for row in grouped.values():
        products, brands = sorted(row.pop("_products")), sorted(row.pop("_brands"))
        rows.append({**row, "held_products": len(products), "brands": ", ".join(brands[:5]),
                     "datasets": ", ".join(sorted(row.pop("_datasets"))), "dsld_ids": ", ".join(products[:10])})
    return sorted(rows, key=lambda r: (-r["held_products"], -r["occurrences"], r["canonical_id"], r["unmapped_form"]))


def build_parent_fallback_rows(parent_fallback_reports: dict) -> list[dict]:
    """Rows whose label names no form: scored at the parent's unknown-form value."""
    grouped: dict[tuple[str, str], dict] = {}
    for dataset, report in parent_fallback_reports.items():
        for entry in (report or {}).get("fallbacks") or []:
            key = (str(entry.get("canonical_id") or ""), str(entry.get("ingredient_normalized") or ""))
            row = grouped.setdefault(key, {
                "canonical_id": key[0], "ingredient": entry.get("ingredient_raw") or key[1],
                "unknown_form": entry.get("fallback_form_name") or "", "occurrences": 0, "_datasets": set(),
            })
            row["occurrences"] += int(entry.get("occurrence_count") or 0)
            row["_datasets"].add(dataset)
    rows = [{**r, "datasets": ", ".join(sorted(r.pop("_datasets")))} for r in grouped.values()]
    return sorted(rows, key=lambda r: (-r["occurrences"], r["canonical_id"], r["ingredient"]))


def _render_form_curation(data, dataset_scope):
    st.write("### Form Curation Queue")
    st.caption(
        "Label forms that hold products from release. disclosed_form_unmapped: a named form the IQM "
        "does not recognize; curate it through /data-fix (alias to an existing form, a new verified "
        "form or parent, a recognized non-scorable ingredient, a typed source/component relationship, "
        "or a rejected compound). pipeline_form_loss: a disclosed form the enricher dropped; repair "
        "the pipeline. identity_mismatch: an IQM form that is not the parent's identity; move it to "
        "its owner. Sorted by held products; click a column to re-sort."
    )
    runs = {name: str(path) for name, path in _scoped(getattr(data, "report_dirs", {}), dataset_scope).items()}
    form_reports = _scoped(data.form_fallback_reports, dataset_scope)
    legacy = sorted(name for name, report in form_reports.items() if "form_fallbacks" not in (report or {}))
    if legacy:
        st.warning(
            f"{len(legacy)} dataset(s) have a form report from before the form contract "
            f"(rows then scored at the parent fallback); re-enrich to queue them: {', '.join(legacy)}"
        )
    form_rows = build_form_curation_rows(form_reports)
    if form_rows:
        data_table(pd.DataFrame(form_rows), max_rows=500)
    else:
        st.info("No disclosed-unmapped forms in the latest enrichment runs.")
    st.write("### Undisclosed Forms (parent fallback)")
    st.caption("The label names no form; the row scores at the parent's unknown-form value. Not a hold.")
    parent_rows = build_parent_fallback_rows(_scoped(data.parent_fallback_reports, dataset_scope))
    if parent_rows:
        data_table(pd.DataFrame(parent_rows), max_rows=500)
    else:
        st.info("No parent-fallback rows in the latest enrichment runs.")
    if runs:
        with st.expander("Report runs read"):
            st.dataframe(pd.DataFrame(sorted(runs.items()), columns=["dataset", "report_dir"]), hide_index=True)


def _render_fallback_tables(data, dataset_scope):
    reports = _scoped_dataset_reports(data, dataset_scope)
    try:
        columns = st.columns(2)
        if not isinstance(columns, (list, tuple)) or len(columns) < 2:
            raise ValueError("columns unavailable")
        left, right = columns[0], columns[1]
    except Exception:
        left, right = st, st
    with left:
        st.write("### Needs Review")
        rows = []
        for dataset, report in reports.items():
            for row in report.get("needs_review_active", []):
                rows.append(
                    {
                        "dataset": dataset,
                        "ingredient_name": row.get("ingredient_name") or row.get("name"),
                        "occurrences": row.get("occurrence_count") or row.get("count") or 1,
                        "type": "active",
                    }
                )
            for row in report.get("needs_review_inactive", []):
                rows.append(
                    {
                        "dataset": dataset,
                        "ingredient_name": row.get("ingredient_name") or row.get("name"),
                        "occurrences": row.get("occurrence_count") or row.get("count") or 1,
                        "type": "inactive",
                    }
                )
        if rows:
            data_table(pd.DataFrame(rows), max_rows=100)
        else:
            st.info("No needs-review ingredient queues found.")
    with right:
        st.write("### Dataset Fallback Signals")
        st.caption("Live fallback and unmapped queues from current dataset output reports.")
        rows = []
        for dataset, report in reports.items():
            rows.append(
                {
                    "dataset": dataset,
                    "cleaned_files": report.get("cleaned_count", 0),
                    "error_files": report.get("error_count", 0),
                    "unmapped_total": len(report.get("unmapped_active", [])) + len(report.get("unmapped_inactive", [])),
                    "last_updated": report.get("latest_activity_at"),
                }
            )
        fallback_df = pd.DataFrame(rows)
        if not fallback_df.empty and "last_updated" in fallback_df.columns and fallback_df["last_updated"].notna().any():
            fallback_df["last_updated"] = pd.to_datetime(fallback_df["last_updated"]).dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M UTC")
        data_table(fallback_df, max_rows=50)


def _provenance_label(entry: dict | None) -> str:
    if not isinstance(entry, dict):
        return "not recorded"
    return f"{entry.get('version', 'unknown')} ({entry.get('fingerprint', 'unknown')})"


def _release_match(name: str, current: dict, release: list[dict]) -> str:
    if not release:
        return "Unknown: no release DB or no config stamp in it"
    total = sum(item["products"] for item in release)
    matching = sum(
        item["products"]
        for item in release
        if isinstance(item.get("provenance"), dict) and item["provenance"].get(name) == current
    )
    if matching == total:
        return f"Yes ({total} products)"
    return f"No ({matching} of {total} products match)"


def build_config_snapshot_rows(data) -> list[dict]:
    """Rows for the Config Snapshot tab, from the production v4 config only.

    Working-tree values come from scoring_v4.config_registry (the scorer's own
    provenance stamp) and quality_score.json pillars; release values come from
    the stamp each released product carries.
    """
    snapshot = data.scoring_config_snapshot or {}
    provenance = snapshot.get("provenance") or {}
    release = snapshot.get("release") or []
    rows = [
        {"field": "Scoring engine (release)", "value": str((data.export_manifest or {}).get("scoring_version", "N/A"))},
        {"field": "Average coverage", "value": f"{data.shared_metrics.get('average_coverage_pct', 'N/A')}%"},
    ]
    for name in sorted(provenance):
        current = provenance[name]
        released = sorted(
            {_provenance_label((item.get("provenance") or {}).get(name)) for item in release}
        )
        rows.append({"field": f"{name} config (working tree)", "value": _provenance_label(current)})
        rows.append({"field": f"{name} config (release)", "value": ", ".join(released) or "not recorded"})
        rows.append({"field": f"{name} matches release", "value": _release_match(name, current, release)})
    weights = snapshot.get("pillar_weights") or {}
    for name, weight in weights.items():
        rows.append({"field": f"{name.replace('_', ' ').title()} max", "value": f"{weight:g}"})
    if weights:
        rows.append({"field": "Pillar total", "value": f"{sum(weights.values()):g}"})
    return rows


def _render_config_snapshot(data):
    st.write("### Config Snapshot")
    if not data.scoring_config_snapshot:
        st.info("The v4 scoring config could not be read.")
        return
    st.caption(
        "Production v4 config: scripts/scoring_v4/config/quality_score.json and "
        "scripts/data/omega_rubric.json, versioned and fingerprinted by "
        "scoring_v4/config_registry.py. Release values are the stamp on each "
        "product in products_core.v4_config_fingerprint."
    )
    st.dataframe(pd.DataFrame(build_config_snapshot_rows(data)), width="stretch", hide_index=True)


def _scoped_dataset_reports(data, dataset_scope):
    if dataset_scope == "All Datasets":
        return data.dataset_reports
    return {dataset_scope: data.dataset_reports.get(dataset_scope, {})} if dataset_scope in data.dataset_reports else {}












