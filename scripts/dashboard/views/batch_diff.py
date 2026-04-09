from __future__ import annotations

import pandas as pd
import streamlit as st


def render_batch_diff(data):
    if len(data.batch_history) < 2:
        st.info("At least two batch logs are required for comparison.")
        return

    labels = [entry["name"] for entry in data.batch_history]
    history_map = {entry["name"]: entry for entry in data.batch_history}
    col1, col2 = st.columns(2)
    with col1:
        base_name = st.selectbox("Batch A", labels, index=1)
    with col2:
        candidate_name = st.selectbox("Batch B", labels, index=0)

    if base_name == candidate_name:
        st.warning("Select two different batch logs.")
        return

    base = history_map[base_name]
    candidate = history_map[candidate_name]
    datasets = sorted(set(base.get("datasets", {}).keys()) | set(candidate.get("datasets", {}).keys()))
    rows = []
    for dataset in datasets:
        base_state = base.get("datasets", {}).get(dataset, {})
        candidate_state = candidate.get("datasets", {}).get(dataset, {})
        rows.append(
            {
                "dataset": dataset,
                "status_a": base_state.get("status", "N/A"),
                "status_b": candidate_state.get("status", "N/A"),
                "stage_a": base_state.get("last_stage", "N/A"),
                "stage_b": candidate_state.get("last_stage", "N/A"),
                "errors_a": len(base_state.get("errors", [])),
                "errors_b": len(candidate_state.get("errors", [])),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
