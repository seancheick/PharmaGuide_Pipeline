from __future__ import annotations

import pandas as pd
import streamlit as st

from scripts.dashboard.components.metric_cards import metric_row
from scripts.dashboard.time_format import format_dashboard_datetime


def render_command_center(data) -> None:
    st.markdown("#### Executive Snapshot")
    metrics = data.shared_metrics
    metric_row(
        [
            ("Products", f"{metrics.get('product_count', 0):,}"),
            ("Avg Score", metrics.get("average_score", "N/A")),
            ("Pipeline Yield", f"{metrics.get('pipeline_yield_pct', 'N/A')}%"),
            ("Export Errors", metrics.get("error_count", 0)),
        ]
    )

    try:
        columns = st.columns([1.4, 1])
        if not isinstance(columns, (list, tuple)) or len(columns) < 2:
            raise ValueError("columns unavailable")
        left, right = columns[0], columns[1]
    except Exception:
        left, right = st, st
    with left:
        st.markdown("#### Timeline Split")
        timeline_rows = pd.DataFrame(
            [
                {
                    "plane": "Release snapshot",
                    "freshness": format_dashboard_datetime(getattr(data, "latest_export_at", None), include_timezone=True),
                    "primary_source": "scripts/final_db_output/",
                },
                {
                    "plane": "Pipeline activity",
                    "freshness": format_dashboard_datetime(getattr(data, "latest_batch_at", None), include_timezone=True),
                    "primary_source": "scripts/products/logs/",
                },
                {
                    "plane": "Dataset outputs",
                    "freshness": format_dashboard_datetime(
                        max(
                            [item for item in [getattr(data, "latest_enriched_at", None), getattr(data, "latest_scored_at", None)] if item is not None],
                            default=None,
                        ),
                        include_timezone=True,
                    ),
                    "primary_source": "scripts/products/output_*",
                },
            ]
        )
        st.dataframe(timeline_rows, width="stretch", hide_index=True)

        if getattr(data, "latest_export_at", None) and getattr(data, "latest_batch_at", None) and data.latest_batch_at > data.latest_export_at:
            st.warning(
                "Release snapshot data is older than current pipeline activity. Treat mixed-plane pages as a blend of shipped and in-flight signals."
            )

    with right:
        st.markdown("#### Immediate Attention")
        attention = []
        if data.shared_metrics.get("error_count", 0):
            attention.append({"priority": "High", "issue": "Errors detected in export or batch history", "go_to": "Observability"})
        if data.shared_metrics.get("safety_counts", {}).get("has_banned_substance", 0):
            attention.append({"priority": "High", "issue": "Banned substances present in current release snapshot", "go_to": "Data Quality"})
        if data.shared_metrics.get("enriched_only_count", 0) or data.shared_metrics.get("scored_only_count", 0):
            attention.append({"priority": "Medium", "issue": "Mismatch counts detected across pipeline stages", "go_to": "Observability"})
        # V4 scoring anomalies — proactively surface scorer bugs (pillars not
        # summing, impossible values, zero-pillar spikes). Guarded: the home
        # page must never crash on the probe; quiet pre-rebuild (no pillar data).
        try:
            from scripts.dashboard.views.scoring_integrity import (
                find_reconciliation_mismatches,
                find_out_of_range,
                find_zero_pillars,
                pillars_present,
            )
            cat = getattr(data, "product_catalog", None)
            thr = getattr(data, "alert_thresholds", {}) or {}
            if cat is not None and not cat.empty:
                recon_n = len(find_reconciliation_mismatches(cat))
                oor_n = len(find_out_of_range(cat))
                if recon_n > int(thr.get("max_recon_mismatches", 0)):
                    attention.append({"priority": "High", "issue": f"{recon_n} products: V4 pillars don't sum to the total score", "go_to": "Scoring Integrity"})
                if oor_n > int(thr.get("max_out_of_range", 0)):
                    attention.append({"priority": "High", "issue": f"{oor_n} products: out-of-range / impossible V4 scores", "go_to": "Scoring Integrity"})
                if pillars_present(cat):
                    zeros = find_zero_pillars(cat)
                    if "quality_score_status" in cat.columns:
                        scored_n = int((cat["quality_score_status"].fillna("scored") == "scored").sum())
                    else:
                        scored_n = len(cat)
                    zero_products = zeros["dsld_id"].nunique() if not zeros.empty else 0
                    zero_pct = (zero_products / scored_n * 100.0) if scored_n else 0.0
                    if zero_pct > float(thr.get("max_zero_pillar_pct", 5.0)):
                        attention.append({"priority": "Medium", "issue": f"{zero_pct:.1f}% of scored products have a 0-valued V4 pillar", "go_to": "Scoring Integrity"})
        except Exception:
            pass
        if not attention:
            attention.append({"priority": "Normal", "issue": "No urgent blockers under current thresholds", "go_to": "Pipeline Health"})
        st.dataframe(pd.DataFrame(attention), width="stretch", hide_index=True)

    st.markdown("#### Navigate By Question")
    shortcuts = pd.DataFrame(
        [
            {"question": "Can we trust the latest release?", "view": "Pipeline Health"},
            {"question": "Why is this product scored this way?", "view": "Product Inspector"},
            {"question": "What changed between releases?", "view": "Release Diff"},
            {"question": "What is breaking in the pipeline?", "view": "Observability"},
            {"question": "Where are quality gaps concentrated?", "view": "Data Quality"},
            {"question": "Which brands and ingredients look strongest?", "view": "Intelligence"},
        ]
    )
    st.dataframe(shortcuts, width="stretch", hide_index=True)
