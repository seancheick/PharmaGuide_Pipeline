from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.dashboard.config import get_config
from scripts.dashboard.data_loader import filter_product_catalog, load_dashboard_data
from scripts.dashboard.app_shell import build_initial_shell_state
from scripts.dashboard.components import inject_dashboard_theme, render_command_center, render_page_frame
from scripts.dashboard.navigation import (
    DEFAULT_VIEW,
    SECTION_BY_VIEW,
    VIEW_SLUGS,
    VIEWS_BY_SECTION,
)
from scripts.dashboard.page_meta import get_page_meta
from scripts.dashboard.time_format import format_dashboard_datetime
from scripts.dashboard.views import (
    render_inspector,
    render_health,
    render_quality, 
    render_observability,
    render_diff,
    render_batch_diff,
    render_intelligence,
    render_audit_section_a,
)

# --- Page Setup ---
st.set_page_config(
    page_title="PharmaGuide Pipeline Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_dashboard_theme()

# --- Config & Data Loading ---
config = get_config()

def refresh_data():
    st.cache_data.clear()
    st.cache_resource.clear()

data = load_dashboard_data(config)

shell_state = build_initial_shell_state(st.query_params, st.session_state)
st.session_state.current_view = shell_state["current_view"]
st.session_state.selected_dsld_id = shell_state["selected_dsld_id"]

# --- Sidebar ---
st.sidebar.title("PharmaGuide")
st.sidebar.caption("Executive analytics workspace")

all_views = list(VIEW_SLUGS.keys())
view = st.sidebar.radio(
    "Page",
    all_views,
    index=all_views.index(st.session_state.current_view)
    if st.session_state.current_view in all_views
    else 0,
)
st.session_state.current_view = view
st.query_params["view"] = VIEW_SLUGS[view]

# Dataset Filter
dataset_options = ["All Datasets"] + data.discovered_datasets
st.sidebar.selectbox(
    "Active Dataset Scope",
    dataset_options,
    key="dataset_filter"
)

catalog = data.product_catalog
score_cap = float(catalog["score"].max()) if not catalog.empty else 100.0
section_a_cap = float(catalog["section_a_max"].fillna(catalog["section_a_score"]).max()) if not catalog.empty else 25.0

st.sidebar.divider()
st.sidebar.caption("Audit filters")

brand_options = sorted([value for value in catalog.get("brand_name", []).dropna().unique().tolist()]) if not catalog.empty else []
supplement_type_options = sorted([value for value in catalog.get("supplement_type", []).dropna().unique().tolist()]) if not catalog.empty else []
primary_category_options = sorted([value for value in catalog.get("primary_category", []).dropna().unique().tolist()]) if not catalog.empty else []
verdict_options = [value for value in ["SAFE", "CAUTION", "POOR", "UNSAFE", "BLOCKED", "NOT_SCORED"] if not catalog.empty and value in set(catalog["verdict"].dropna().tolist())]

st.sidebar.multiselect("Brand", brand_options, key="brand_filter")
st.sidebar.multiselect("Supplement Type", supplement_type_options, key="supplement_type_filter")
st.sidebar.multiselect("Primary Category", primary_category_options, key="primary_category_filter")
st.sidebar.multiselect("Verdict", verdict_options, key="verdict_filter")
st.sidebar.slider("Minimum Score", 0.0, max(score_cap, 100.0), 0.0, 1.0, key="min_score_filter")
st.sidebar.slider("Minimum Section A", 0.0, max(section_a_cap, 25.0), 0.0, 0.5, key="min_section_a_filter")
st.sidebar.checkbox("Section A ceiling only", key="only_section_a_ceiling")
st.sidebar.checkbox("Only harmful findings", key="only_harmful_flags")
st.sidebar.checkbox("Only omega-3 products", key="only_omega_bonus_candidates")
st.sidebar.checkbox("Only verified Non-GMO", key="only_non_gmo_verified")
filtered_catalog = filter_product_catalog(data)
st.sidebar.caption(f"Filtered products: {len(filtered_catalog)} / {len(catalog)}")

# Refresh Button
if st.sidebar.button("🔄 Force Data Refresh"):
    refresh_data()
    st.rerun()

st.sidebar.divider()
st.sidebar.caption("Data planes")
st.sidebar.caption("Release Snapshot")
st.sidebar.caption("Pipeline Logs")
st.sidebar.caption("Dataset Outputs")
st.sidebar.divider()
st.sidebar.caption(f"Last export: {format_dashboard_datetime(data.latest_export_at, style='compact')}")
st.sidebar.caption(f"Last batch: {format_dashboard_datetime(data.latest_batch_at, style='compact')}")
st.sidebar.caption(f"Latest dataset: {format_dashboard_datetime(max([item for item in [data.latest_enriched_at, data.latest_scored_at] if item is not None], default=None), style='compact')}")

# Warnings
with st.sidebar.expander(f"Warnings ({len(data.warnings)})"):
    st.caption(f"Showing latest discovered reports from {config.scan_dir}")
    st.caption(f"Release data from {config.build_root}")
    if data.warnings:
        for warning in data.warnings:
            st.warning(warning)
    else:
        st.caption("No loader warnings.")

dataset_activity = max([item for item in [data.latest_enriched_at, data.latest_scored_at] if item is not None], default=None)
st.markdown(
    f"""
    <div class="pg-shell-hero">
      <div class="pg-shell-kicker">Executive Analytics UI</div>
      <h1 class="pg-shell-title">PharmaGuide Pipeline Dashboard</h1>
      <div class="pg-shell-summary">
        Release snapshot: {format_dashboard_datetime(data.latest_export_at, include_timezone=True)}
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Pipeline activity: {format_dashboard_datetime(data.latest_batch_at, include_timezone=True)}
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Dataset activity: {format_dashboard_datetime(dataset_activity, include_timezone=True)}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
if data.latest_export_at and data.latest_batch_at and data.latest_batch_at > data.latest_export_at:
    st.warning(
        "Release snapshot data is older than current pipeline activity. Some pages blend shipped release data with newer pipeline or dataset signals."
    )


def _render_current_view() -> None:
    if view == "Command Center":
        render_command_center(data)
    elif view == "Product Inspector":
        render_inspector(data)
    elif view == "Pipeline Health":
        render_health(data)
    elif view == "Data Quality":
        render_quality(data)
    elif view == "Section A Audit":
        render_audit_section_a(data)
    elif view == "Observability":
        render_observability(data)
    elif view == "Release Diff":
        render_diff(data)
    elif view == "Batch Diff":
        render_batch_diff(data)
    elif view == "Intelligence":
        render_intelligence(data)


page_meta = get_page_meta(VIEW_SLUGS.get(view, VIEW_SLUGS[DEFAULT_VIEW]), data)
render_page_frame(page_meta, _render_current_view)

# --- Footer ---
st.divider()
st.caption(f"Build Root: {config.build_root}")
st.caption(f"Scan Dir: {config.scan_dir}")
