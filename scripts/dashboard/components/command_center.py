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

    left, right = st.columns([1.4, 1])
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
        st.dataframe(timeline_rows, use_container_width=True, hide_index=True)

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
        if not attention:
            attention.append({"priority": "Normal", "issue": "No urgent blockers under current thresholds", "go_to": "Pipeline Health"})
        st.dataframe(pd.DataFrame(attention), use_container_width=True, hide_index=True)

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
    st.dataframe(shortcuts, use_container_width=True, hide_index=True)
