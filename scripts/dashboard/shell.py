"""App shell: global plane/run controls, provenance banner, cached index reads.

Reads are cached per index build, so a new build invalidates them automatically and a
normal page load never parses source JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import pyarrow.dataset as pds
import streamlit as st

from scripts.dashboard import findings_rules, run_compare, score_index, triage
from scripts.dashboard.components.ui import chip, empty_index_notice
from scripts.dashboard.time_format import format_dashboard_datetime

PLANES = {"candidate": "Candidate", "release": "Release", "backfill": "Historical"}
PAGE_OBJECTS: dict[str, Any] = {}  # slug -> st.Page, filled by app.py


def go(slug: str, **state: Any) -> None:
    """Navigate to another page, carrying session state (e.g. the product to trace)."""
    if "trace_dsld_id" in state:
        for key in ("trace_query", "trace_pick"):
            st.session_state.pop(key, None)
    for key, value in state.items():
        if key in ("plane", "run"):
            pending = dict(st.session_state.get("navigation_run") or {})
            pending[key] = value
            st.session_state["navigation_run"] = pending
            st.query_params[key] = value
        else:
            st.session_state[key] = value
    if slug in PAGE_OBJECTS:
        st.switch_page(PAGE_OBJECTS[slug])


@st.cache_data(show_spinner=False, max_entries=64)
def _read(build: str, run_key: str, table: str, columns: tuple[str, ...] | None = None) -> pd.DataFrame:
    directory = f"{build}/runs/{run_key}/{table}"
    schema = score_index.TABLES[table]
    try:
        return pds.dataset(directory, format="parquet", schema=schema).to_table(
            columns=list(columns) if columns else None).to_pandas()
    except (FileNotFoundError, OSError):
        return pd.DataFrame(columns=list(columns) if columns else schema.names)


@st.cache_data(show_spinner=False, max_entries=16)
def _deltas(build: str, base: str, cand: str, runs_json: str) -> pd.DataFrame:
    path = f"{build}/deltas/{base}__{cand}__v{run_compare.DELTA_VERSION}.parquet"
    try:
        return pd.read_parquet(path)
    except (FileNotFoundError, OSError):
        runs = {run["run_key"]: run for run in json.loads(runs_json)}
        return run_compare.compare(lambda key, table, columns=None: _read(build, key, table, tuple(columns) if columns else None),
                                   runs[base], runs[cand])


@dataclass
class PageContext:
    data: Any
    index: score_index.IndexReader
    plane: str
    run_key: str | None
    maxima: dict[str, float] = field(default_factory=score_index.pillar_maxima)

    @property
    def build(self) -> str:
        return str(self.index.build) if self.index.build else ""

    @property
    def run(self) -> dict[str, Any] | None:
        return self.index.run(self.run_key)

    @property
    def ready(self) -> bool:
        return self.index.available and self.run_key is not None

    def frame(self, table: str, run_key: str | None = None, columns: list[str] | None = None) -> pd.DataFrame:
        key = run_key or self.run_key
        if not self.build or key is None:
            return pd.DataFrame(columns=columns or score_index.TABLES[table].names)
        return _read(self.build, key, table, tuple(columns) if columns else None)

    def products(self, run_key: str | None = None) -> pd.DataFrame:
        return self.frame("products", run_key)

    def runs(self, plane: str | None = None) -> list[dict[str, Any]]:
        return [run for run in self.index.runs() if plane is None or run["plane"] == plane]

    def baseline_key(self) -> str | None:
        """Default comparison: release for a candidate run, else the previous run of the same plane."""
        if self.plane == "candidate" and self.index.latest("release") and self.run_key != self.index.latest("release"):
            return self.index.latest("release")
        selected = (self.run or {}).get("run_time") or ""
        earlier = [run["run_key"] for run in self.runs(self.plane)
                   if run["run_key"] != self.run_key and (run.get("run_time") or "") <= selected]
        return earlier[-1] if earlier else None

    def deltas(self, base: str | None, cand: str | None) -> pd.DataFrame:
        if not base or not cand or not self.build:
            return pd.DataFrame()
        return _deltas(self.build, base, cand, json.dumps(self.index.runs(), default=str))

    def findings(self) -> pd.DataFrame:
        found = self.index.findings()
        if found.empty or not self.build:
            return found
        found = findings_rules.with_seen(found, self.index.build, self.index.runs())
        found["config_fingerprint"] = None
        for run in self.index.runs():
            mask = found["run_key"] == run["run_key"]
            if mask.any():
                products = self.frame("products", run["run_key"], ["dsld_id", "config_fingerprint"])
                stamps = products.set_index("dsld_id")["config_fingerprint"]
                found.loc[mask, "config_fingerprint"] = found.loc[mask, "dsld_id"].map(stamps)
        scopes = {run["run_key"]: run.get("config_fingerprints") or [] for run in self.index.runs()}
        return triage.merge(found, config_versions=[], run_configs=scopes)


def init(data: Any) -> PageContext:
    """Sidebar controls shared by every page; returns the page context."""
    index: score_index.IndexReader = data.index
    for key, value in st.session_state.pop("navigation_run", {}).items():
        st.session_state[key] = value
    params = st.query_params
    with st.sidebar:
        st.markdown("**PharmaGuide** · Quality control")
        plane = st.segmented_control("Plane", list(PLANES), default=params.get("plane", "candidate")
                                     if params.get("plane", "candidate") in PLANES else "candidate",
                                     format_func=PLANES.get, key="plane", width="stretch",
                                     help="Candidate = newest scored pipeline output (not yet published). "
                                          "Release = the catalog that ships.") or "candidate"
        runs = [run for run in index.runs() if run["plane"] == plane]
        run_key = None
        if runs:
            labels = {run["run_key"]: _run_label(run) for run in reversed(runs)}
            wanted = params.get("run") if params.get("run") in labels else index.latest(plane) or next(iter(labels))
            run_key = st.selectbox("Run", list(labels), index=list(labels).index(wanted), format_func=labels.get, key="run")
        params["plane"] = plane
        if run_key:
            params["run"] = run_key
        _index_status(index)
    return PageContext(data=data, index=index, plane=plane, run_key=run_key)


def _run_label(run: dict[str, Any]) -> str:
    when = format_dashboard_datetime(run.get("run_time"), style="compact")
    versions = ", ".join(v for v in run.get("config_versions") or [] if v) or "config ?"
    return f"{when} · {versions.split('-')[0]} · {run.get('products', 0):,}"


@st.cache_data(ttl=30, show_spinner=False)
def _cached_staleness(build: str, scan_dir: str, build_root: str, cache_root: str) -> dict[str, Any]:
    return score_index.IndexReader(score_index.default_paths(scan_dir, build_root, cache_root)).staleness()


def _staleness(index: score_index.IndexReader) -> dict[str, Any]:
    paths = index.paths
    return _cached_staleness(str(index.build), str(paths.scan_dir), str(paths.build_root), str(paths.cache_root))


def _index_status(index: score_index.IndexReader) -> None:
    st.divider()
    if not index.available:
        st.warning("Index not built", icon=":material/database:")
    else:
        stale = _staleness(index)
        built = format_dashboard_datetime(index.meta.get("built_at"), style="compact")
        if stale["stale"]:
            changed = len(stale["candidate_changed"]) + len(stale["candidate_removed"])
            reasons = ([f"{changed} batch(es) changed"] if changed else [])
            if stale["release_changed"]:
                reasons.append("release changed")
            if stale.get("projection_changed"):
                reasons.append("dashboard projection changed")
            detail = "; ".join(reasons) or "source changed"
            st.warning(f"Index is stale — {detail}. Built {built}.", icon=":material/update:")
        else:
            st.caption(f":material/check_circle: Index fresh · built {built}")
    if st.button("Refresh index", icon=":material/refresh:", width="stretch",
                 help="Re-reads changed scored batches and release blobs only. Never runs the pipeline."):
        with st.status("Refreshing the dashboard index…", expanded=True) as status:
            bar = st.progress(0.0)
            try:
                score_index.refresh(index.paths, progress=lambda message, fraction: bar.progress(min(fraction, 1.0), text=message))
            except score_index.IndexBusy:
                status.update(label="Another refresh is running", state="error")
                return
            except Exception as exc:  # the last good build stays current; show why
                status.update(label=f"Refresh failed — kept the previous build: {exc}", state="error")
                return
            status.update(label="Index refreshed", state="complete")
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
    st.caption("CLI: `python -m scripts.dashboard.score_index refresh`")


def banner(ctx: PageContext) -> bool:
    """Provenance line on every page. Returns False when there is nothing to show."""
    if not ctx.index.available:
        empty_index_notice("python -m scripts.dashboard.score_index refresh")
        return False
    run = ctx.run or {}
    when = format_dashboard_datetime(run.get("run_time"), style="full")
    parts = [
        chip(PLANES.get(ctx.plane, ctx.plane), "accent"),
        f"<b>Run</b> {when}",
        f"<b>Config</b> {', '.join(v for v in run.get('config_versions') or [] if v) or '—'}",
        f"<b>Fidelity</b> {str(run.get('fidelity', '—')).replace('_', ' ')}",
        f"<b>Products</b> {run.get('products', 0):,}",
    ]
    if ctx.plane == "candidate":
        parts.append("not yet published")
    sha = ctx.index.meta.get("dashboard_indexer_git_sha")
    parts.append(f"indexed by dashboard {sha[:9] if sha else '—'} (indexer code, not the scorer's)")
    st.markdown('<div class="pg-banner">' + " &nbsp;·&nbsp; ".join(parts) + "</div>", unsafe_allow_html=True)
    return ctx.run_key is not None
