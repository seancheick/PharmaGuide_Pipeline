from __future__ import annotations

from collections.abc import Callable
from html import escape
from typing import Any

import streamlit as st

from scripts.dashboard.components.source_chips import render_source_chips


def _safe_streamlit_call(name: str, *args: Any, **kwargs: Any) -> Any:
    try:
        fn = getattr(st, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    except Exception:
        return None
    return None


def inject_dashboard_theme() -> None:
    _safe_streamlit_call(
        "markdown",
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Source+Serif+4:wght@600;700&display=swap');

        :root {
          --pg-slate-900: #0f172a;
          --pg-slate-800: #1e293b;
          --pg-slate-700: #334155;
          --pg-slate-600: #475569;
          --pg-slate-500: #64748b;
          --pg-slate-100: #f1f5f9;
          --pg-white: #ffffff;
          --pg-teal-50: #ecfdf5;
          --pg-teal-500: #14b8a6;
          --pg-teal-600: #0d9488;
          --pg-amber-500: #f59e0b;
          --pg-emerald-500: #10b981;
          --pg-red-500: #ef4444;
          --pg-card: rgba(255,255,255,0.94);
        }

        body, .stApp {
          font-family: 'Inter', sans-serif;
          color: var(--pg-slate-900);
        }

        button, input, select, textarea {
          font-family: 'Inter', sans-serif !important;
          font-size: 0.95rem !important;
        }

        .stButton>button,
        [data-testid="stSidebar"] button {
          border-radius: 999px !important;
          padding: 0.75rem 1rem !important;
          min-height: 2.8rem !important;
          font-weight: 600 !important;
        }

        .stTextInput>div>label,
        .stSelectbox>div>label,
        .stTextInput>label,
        .stSelectbox>label {
          font-size: 0.95rem !important;
          color: var(--pg-slate-700) !important;
        }

        .stTextInput>div>div>input,
        .stSelectbox>div>div>div {
          font-size: 0.96rem !important;
          border-radius: 14px !important;
          padding: 0.8rem 1rem !important;
        }

        .stDataFrame table {
          font-family: 'Inter', sans-serif;
          font-size: 0.92rem;
        }

        .stDataFrame th, .stDataFrame td {
          padding: 0.7rem 0.9rem !important;
        }

        .stMarkdown h1,
        .stMarkdown h2,
        .stMarkdown h3,
        .stMarkdown h4 {
          margin-top: 1rem;
          margin-bottom: 0.45rem;
          line-height: 1.1;
        }

        .stMarkdown h1 { font-size: 1.95rem; }
        .stMarkdown h2 { font-size: 1.35rem; }
        .stMarkdown h3 { font-size: 1.15rem; }

        .stAlert {
          border-radius: 20px !important;
        }

        [data-testid="stSidebar"] {
          background: linear-gradient(180deg, #0f172a 0%, #132338 100%);
          border-right: 1px solid rgba(255,255,255,0.08);
        }

        [data-testid="stSidebar"] * {
          color: #e2e8f0 !important;
        }

        .pg-shell-hero {
          border-radius: 24px;
          padding: 22px 26px;
          background: linear-gradient(135deg, #0f172a 0%, #123047 62%, #0d9488 140%);
          color: white;
          box-shadow: 0 22px 56px rgba(15, 23, 42, 0.18);
          margin-bottom: 1.15rem;
        }

        .pg-shell-kicker {
          font-family: 'Plus Jakarta Sans', sans-serif;
          font-size: 0.78rem;
          letter-spacing: 0.16em;
          text-transform: uppercase;
          opacity: 0.82;
          margin-bottom: 0.3rem;
        }

        .pg-shell-title {
          font-family: 'Source Serif 4', serif;
          font-size: 2.15rem;
          line-height: 1.08;
          margin: 0;
        }

        .pg-shell-summary {
          margin-top: 0.75rem;
          color: rgba(255,255,255,0.88);
          font-size: 0.98rem;
          max-width: 60rem;
        }

        .pg-page-card {
          background: rgba(255,255,255,0.92);
          border: 1px solid rgba(15, 23, 42, 0.08);
          border-radius: 20px;
          padding: 1.1rem 1.2rem;
          box-shadow: 0 14px 38px rgba(15, 23, 42, 0.06);
        }

        .pg-page-eyebrow {
          font-family: 'Plus Jakarta Sans', sans-serif;
          text-transform: uppercase;
          letter-spacing: 0.12em;
          font-size: 0.75rem;
          color: var(--pg-teal-600);
          margin-bottom: 0.35rem;
        }

        .pg-page-title {
          font-family: 'Source Serif 4', serif;
          font-size: 2rem;
          margin: 0 0 0.35rem 0;
          color: var(--pg-slate-900);
        }

        .pg-page-summary {
          font-family: 'Inter', sans-serif;
          color: var(--pg-slate-600);
          font-size: 0.98rem;
          margin-bottom: 0.6rem;
        }

        .pg-context-card {
          background: linear-gradient(180deg, rgba(240,253,250,0.96) 0%, rgba(255,255,255,0.98) 100%);
          border: 1px solid rgba(20,184,166,0.20);
          border-radius: 20px;
          padding: 1rem 1rem 0.75rem 1rem;
          box-shadow: 0 14px 30px rgba(20, 184, 166, 0.08);
        }

        .pg-context-heading {
          font-family: 'Plus Jakarta Sans', sans-serif;
          font-size: 0.82rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--pg-slate-700);
          margin: 0 0 0.55rem 0;
        }

        .pg-context-list {
          margin: 0 0 1rem 0;
          padding-left: 1rem;
          color: var(--pg-slate-700);
          font-family: 'Inter', sans-serif;
          font-size: 0.9rem;
        }

        .pg-mobile-context {
          display: none;
          margin-top: 1rem;
          border: 1px solid rgba(20,184,166,0.20);
          border-radius: 18px;
          background: rgba(255,255,255,0.94);
          box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
          overflow: hidden;
        }

        .pg-mobile-context summary {
          list-style: none;
          cursor: pointer;
          padding: 0.95rem 1rem;
          font-family: 'Plus Jakarta Sans', sans-serif;
          font-size: 0.86rem;
          font-weight: 700;
          color: var(--pg-slate-900);
          background: linear-gradient(180deg, rgba(240,253,250,0.96) 0%, rgba(255,255,255,0.98) 100%);
        }

        .pg-mobile-context summary::-webkit-details-marker {
          display: none;
        }

        .pg-mobile-context-body {
          padding: 0.35rem 1rem 0.6rem 1rem;
        }

        @media (max-width: 1100px) {
          .pg-mobile-context {
            display: block;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_context_sections(meta: dict[str, Any]) -> None:
    for item in meta.get("freshness_display", []):
        _safe_streamlit_call("caption", f"{item['label']}: {item['value']}")

    _safe_streamlit_call("markdown", '<div class="pg-context-heading">Data Sources</div>', unsafe_allow_html=True)
    for path in meta.get("source_paths", []):
        _safe_streamlit_call("caption", path)

    _safe_streamlit_call("markdown", '<div class="pg-context-heading">How To Read This Page</div>', unsafe_allow_html=True)
    for note in meta.get("usage_notes", []):
        _safe_streamlit_call("markdown", f"- {note}")

    _safe_streamlit_call("markdown", '<div class="pg-context-heading">Related Views</div>', unsafe_allow_html=True)
    for view in meta.get("related_views", []):
        _safe_streamlit_call("caption", view)


def _build_mobile_context_html(meta: dict[str, Any]) -> str:
    freshness_items = "".join(
        f"<li><strong>{escape(item['label'])}:</strong> {escape(item['value'])}</li>"
        for item in meta.get("freshness_display", [])
    )
    source_items = "".join(
        f"<li>{escape(path)}</li>"
        for path in meta.get("source_paths", [])
    )
    note_items = "".join(
        f"<li>{escape(note)}</li>"
        for note in meta.get("usage_notes", [])
    )
    related_items = "".join(
        f"<li>{escape(view)}</li>"
        for view in meta.get("related_views", [])
    )
    return f"""
    <details class="pg-mobile-context">
      <summary>Open context panel below the page body</summary>
      <div class="pg-mobile-context-body">
        <div class="pg-context-heading">Freshness &amp; Context</div>
        <ul class="pg-context-list">{freshness_items}</ul>
        <div class="pg-context-heading">Data Sources</div>
        <ul class="pg-context-list">{source_items}</ul>
        <div class="pg-context-heading">How To Read This Page</div>
        <ul class="pg-context-list">{note_items}</ul>
        <div class="pg-context-heading">Related Views</div>
        <ul class="pg-context-list">{related_items}</ul>
      </div>
    </details>
    """


def render_page_frame(meta: dict[str, Any], body_renderer: Callable[[], None]) -> None:
    try:
        columns = st.columns([3.6, 1.35])
    except Exception:
        columns = []
    if not isinstance(columns, (list, tuple)) or len(columns) < 2:
        body_renderer()
        return
    main_col, side_col = columns[:2]

    with main_col:
        _safe_streamlit_call(
            "markdown",
            f"""
            <div class="pg-page-card">
              <div class="pg-page-eyebrow">Dashboard View</div>
              <div class="pg-page-title">{meta['page_title']}</div>
              <div class="pg-page-summary">{meta['page_summary']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_source_chips(meta["data_planes"])
        if meta.get("show_mixed_plane_warning"):
            _safe_streamlit_call("warning", meta["mixed_plane_warning"])
        body_renderer()

    with side_col:
        _safe_streamlit_call(
            "markdown",
            """
            <div class="pg-context-card">
              <div class="pg-context-heading">Freshness & Context</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _render_context_sections(meta)

    # Fallback access path for narrower layouts where the right rail becomes cramped.
    _safe_streamlit_call("markdown", _build_mobile_context_html(meta), unsafe_allow_html=True)
