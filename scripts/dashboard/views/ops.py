"""Data Quality, Release & Ops: pipeline health, batches, data quality, index status."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from scripts.dashboard import score_index, shell
from scripts.dashboard.views.batch_diff import render_batch_diff
from scripts.dashboard.views.health import render_health
from scripts.dashboard.views.quality import render_quality


def render(ctx: shell.PageContext) -> None:
    tabs = st.tabs(["Pipeline health", "Data quality", "Batch diff", "Dashboard index"])
    with tabs[0]:
        render_health(ctx.data)
    with tabs[1]:
        render_quality(ctx.data)
    with tabs[2]:
        render_batch_diff(ctx.data)
    with tabs[3]:
        _index_status(ctx)


def _index_status(ctx: shell.PageContext) -> None:
    index = ctx.index
    status_path = index.paths.status_file
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    st.caption(f"Cache: {index.paths.cache_root}")
    if status:
        (st.success if status.get("ok") else st.error)(
            f"Last refresh {'succeeded' if status.get('ok') else 'failed'} at {status.get('at')}"
            + (f" in {status.get('seconds')} s" if status.get("seconds") else "")
            + (f": {status.get('error')} (kept build {status.get('kept_build')})" if status.get("error") else ""))
    if not index.available:
        st.code("python -m scripts.dashboard.score_index refresh", language="bash")
        return
    meta = index.meta
    st.dataframe(pd.DataFrame([
        {"field": "Build", "value": meta.get("build_id")},
        {"field": "Built at", "value": meta.get("built_at")},
        {"field": "Index schema", "value": meta.get("index_schema_version")},
        {"field": "Indexer version", "value": meta.get("index_build_version")},
        {"field": "Projection fingerprint", "value": meta.get("projection_fingerprint")},
        {"field": "Dashboard indexer git SHA", "value": meta.get("dashboard_indexer_git_sha")},
        {"field": "Scan dir (candidate)", "value": meta.get("scan_dir")},
        {"field": "Build root (release)", "value": meta.get("build_root")},
        {"field": "Refresh seconds", "value": meta.get("refresh_seconds")},
    ]).astype(str), hide_index=True, width="stretch")
    runs = pd.DataFrame([{k: run.get(k) for k in ("run_key", "plane", "fidelity", "run_time", "products",
                                                  "config_versions", "source")} for run in index.runs()])
    st.dataframe(runs.astype(str), hide_index=True, width="stretch")
    staleness = index.staleness()
    st.json(staleness, expanded=False)
    cols = st.columns(2)
    with cols[0].popover("Backfill older catalogs", icon=":material/history:"):
        st.caption("Adds older pharmaguide_core.db catalogs as pillar-totals-only runs (deduplicated).")
        paths = st.text_area("One DB path per line", key="ops_backfill")
        if st.button("Backfill", key="ops_backfill_go") and paths.strip():
            result = score_index.backfill(index.paths, [line.strip() for line in paths.splitlines() if line.strip()])
            st.success(f"Added {len(result['added'])} run(s).")
            st.cache_data.clear()
    if cols[1].button("Remove old builds (keep 2)", icon=":material/delete_sweep:"):
        st.success(f"Removed {len(score_index.gc(index.paths))} build(s).")
