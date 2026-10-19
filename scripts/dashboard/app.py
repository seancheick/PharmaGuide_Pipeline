from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.dashboard import shell  # noqa: E402
from scripts.dashboard.components.page_frame import render_page_frame  # noqa: E402
from scripts.dashboard.components.theme import inject_theme  # noqa: E402
from scripts.dashboard.config import get_config  # noqa: E402
from scripts.dashboard.data_loader import load_dashboard_data  # noqa: E402
from scripts.dashboard.navigation import DEFAULT_SLUG, PAGES, resolve_legacy_view  # noqa: E402
from scripts.dashboard.page_meta import get_page_meta  # noqa: E402
from scripts.dashboard.views import (  # noqa: E402
    audit_queue, coverage, explorer, market, ops, overview, run_compare_view, safety, score_lab, trace,
)

VIEWS = {module.__name__.rsplit(".", 1)[-1]: module for module in
         (overview, audit_queue, run_compare_view, explorer, trace, score_lab, coverage, market, safety, ops)}

st.set_page_config(page_title="PharmaGuide Quality Control", page_icon=":material/verified:",
                   layout="wide", initial_sidebar_state="expanded")
inject_theme()

config = get_config()
data = load_dashboard_data(config)
ctx = shell.init(data)


def _page(spec):
    def render() -> None:
        module = VIEWS[spec.module]
        render_page_frame(get_page_meta(spec.slug, data), lambda: module.render(ctx))
    render.__name__ = f"page_{spec.module}"
    return st.Page(render, title=spec.title, icon=spec.icon, url_path=spec.slug, default=spec.slug == DEFAULT_SLUG)


pages = {spec.slug: _page(spec) for spec in PAGES}
shell.PAGE_OBJECTS.update(pages)
sections: dict[str, list] = {}
for spec in PAGES:
    sections.setdefault(spec.section, []).append(pages[spec.slug])
navigation = st.navigation(sections)

legacy = resolve_legacy_view(st.query_params.get("view"))
if legacy:
    dsld_id = st.query_params.get("dsld_id")
    del st.query_params["view"]
    if dsld_id:
        st.session_state["trace_dsld_id"] = dsld_id
    st.switch_page(pages[legacy])

navigation.run()
