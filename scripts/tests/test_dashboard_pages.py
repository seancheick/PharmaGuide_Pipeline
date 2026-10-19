"""Dashboard pages, explorer filters and read-only guards. Hermetic (tmp index), CI-safe."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd
import pytest

from dashboard_index_fixtures import scored_product, write_batch, write_release
from scripts.dashboard import saved_views as sv
from scripts.dashboard import score_index as si
from scripts.dashboard.navigation import LEGACY_VIEW_SLUGS, PAGE_BY_SLUG, PAGES, resolve_legacy_view
from scripts.dashboard.views import market, score_lab

DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard"


@pytest.fixture
def indexed(tmp_path, monkeypatch):
    scan, dist, cache = tmp_path / "products", tmp_path / "dist", tmp_path / "cache"
    monkeypatch.setenv("PG_DASHBOARD_CACHE", str(cache))
    monkeypatch.setenv("PG_DASHBOARD_REVIEW", str(tmp_path / "review"))
    products = [
        scored_product("1"), scored_product("2", dose_neutral=True, verification_neutral=True),
        scored_product("3", status="suppressed_safety", safety="blocked"),
        scored_product("4", deduction=3.0, floor=True), scored_product("5", status="not_scored", assessment="partial"),
        scored_product("6", evidence_score=0.0, evidence_state="applicability_unestablished"),
        scored_product("7", assessment="partial", extra_receipt=[
            ("dose", {"id": "dose_safety_ceiling", "kind": "cap", "source": "x", "points": 0.0})]),
    ]
    write_batch(scan, "Acme", products)
    write_release(dist, products[:4])
    si.refresh(si.default_paths(scan, dist, cache))
    return scan, dist


def test_every_page_renders_against_a_real_index(dashboard_app, indexed):
    scan, dist = indexed
    data = dashboard_app.load_dashboard_data(dashboard_app.DashboardConfig(scan_dir=scan, build_root=dist))
    ctx = dashboard_app.shell.init(data)
    assert ctx.ready and ctx.plane == "candidate"
    for spec in dashboard_app.navigation.PAGES:
        module = dashboard_app.view(spec.module)
        dashboard_app.render_page_frame(dashboard_app.get_page_meta(spec.slug, data), lambda: module.render(ctx))
    release = dashboard_app.shell.PageContext(data=data, index=ctx.index, plane="release",
                                              run_key=ctx.index.latest("release"))
    for spec in dashboard_app.navigation.PAGES:
        dashboard_app.view(spec.module).render(release)
    dashboard_app.st.session_state["trace_dsld_id"] = "4"
    dashboard_app.view("trace").render(ctx)


def _frame(indexed, plane="candidate"):
    scan, dist = indexed
    reader = si.IndexReader(si.default_paths(scan, dist))
    return reader.frame(reader.latest(plane), "products")


@pytest.mark.parametrize("plane", ["candidate", "release"])
def test_every_saved_view_runs_on_both_planes(indexed, plane):
    frame = sv.attach_comparison(_frame(indexed, plane), None, release=None)
    for name, spec in sv.SAVED_VIEWS.items():
        result = sv.apply_filters(frame, spec)
        assert set(result.columns) == set(frame.columns), name


def test_filters_select_the_expected_products(indexed):
    frame = sv.attach_comparison(_frame(indexed), None, release=None)
    ids = lambda spec: set(sv.apply_filters(frame, spec)["dsld_id"])  # noqa: E731
    assert ids(sv.SAVED_VIEWS["Evidence = 0 (all states)"]) == {"6"}
    assert ids(sv.SAVED_VIEWS["Evidence applicability gaps"]) == {"6"}
    assert ids(sv.SAVED_VIEWS["Dose neutral"]) == {"2"}
    assert ids(sv.SAVED_VIEWS["Verification unknown (neutral 6)"]) == {"2"}
    assert ids(sv.SAVED_VIEWS["Floors absorbing deductions"]) == {"4"}
    assert ids({"fully_absorbed": True}) == {"4"}
    assert ids(sv.SAVED_VIEWS["Dose capped by safety ceiling"]) == {"7"}
    assert ids(sv.SAVED_VIEWS["Partial products in rankings"]) == {"7"}
    assert ids(sv.SAVED_VIEWS["Suppressed or not scored"]) == {"3", "5"}
    assert ids({"pillar_zero": ["evidence"]}) == {"6"}
    assert ids({"entry_ids": ["botanical_formulation_bounds"]}) == {"4"}
    assert ids({"has_cap": True}) == {"7"}
    assert ids({"pillar_range": {"dose": (11.0, 12.0)}}) == {"2"}
    assert ids({"search": "product 4"}) == {"4"}
    with pytest.raises(KeyError):
        sv.apply_filters(frame, {"no_such_filter": True})


def test_candidate_release_flags_use_the_shipped_rounding(indexed):
    candidate, release = _frame(indexed), _frame(indexed, "release")
    flagged = sv.attach_comparison(candidate, None, release=release).set_index("dsld_id")
    assert not flagged.loc["1", "differs_from_release"]          # same product, whole-number release total
    assert not flagged.loc["5", "differs_from_release"]          # absent from release: nothing to differ from


def test_leaderboard_needs_complete_products_and_a_minimum_count():
    rows = [{"dsld_id": str(i), "brand_name": "Big", "quality_score_status": "scored", "quality_assessment_status": "complete",
             "total": 70.0 + i, "verification_cert": 0.0} for i in range(6)]
    rows += [{"dsld_id": "s1", "brand_name": "Small", "quality_score_status": "scored", "quality_assessment_status": "complete",
              "total": 99.0, "verification_cert": 4.0}]
    rows += [{"dsld_id": f"p{i}", "brand_name": "Partial", "quality_score_status": "scored",
              "quality_assessment_status": "partial", "total": 95.0, "verification_cert": 0.0} for i in range(6)]
    board = market.brand_leaderboard(pd.DataFrame(rows), pd.DataFrame(columns=["dsld_id"]), min_products=5)
    assert list(board["brand_name"]) == ["Big"]
    assert board.iloc[0]["ranked_products"] == 6 and board.iloc[0]["completeness_pct"] == 100.0


def test_peer_percentile_is_context_with_a_denominator():
    rows = [{"dsld_id": str(i), "product_name": "p", "brand_name": "b", "category": "big" if i < 35 else "tiny",
             "quality_score_status": "scored", "quality_assessment_status": "complete", "total": float(i)} for i in range(40)]
    out = score_lab.peer_percentiles(pd.DataFrame(rows))
    assert set(out["category"]) == {"big"} and (out["peer_n"] == 35).all()
    assert out["peer_percentile"].between(0, 100).all()
    assert "score" not in " ".join(out.columns).replace("total", "")


def test_legacy_view_links_resolve_to_new_pages():
    assert all(slug in PAGE_BY_SLUG for slug in LEGACY_VIEW_SLUGS.values())
    assert resolve_legacy_view("product-inspector") == "product-trace"
    assert resolve_legacy_view("overview") == "overview"
    assert resolve_legacy_view("nope") is None
    assert len({page.slug for page in PAGES}) == len(PAGES)


# ---------------------------------------------------------------- read-only guards

def _sources():
    return {path: path.read_text(encoding="utf-8") for path in DASHBOARD.rglob("*.py")}


def test_dashboard_never_imports_a_scorer_executor():
    banned = ("score_supplements_v4", "scoring_v4.modules", "assemble_quality_score", "score_product_v4",
              "enrich_supplements_v3", "build_final_db")
    for path, text in _sources().items():
        tree = ast.parse(text)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [alias.name for alias in node.names]
            for name in names:
                assert not any(b in name for b in banned), f"{path.name} imports {name}"


def test_dashboard_writes_only_to_its_cache():
    writers = re.compile(r"\.(write_text|write_bytes|mkdir|unlink)\(|\.to_(csv|parquet)\((?!\s*index=|\s*buffer)|\.rename\((?!\s*columns=|\")|open\([^)]*['\"]w|os\.replace|shutil\.rmtree|pq\.write_table")
    # cache/review writers; capture_screenshots is a dev tool writing PNGs (in-memory exports don't count)
    allowed = {"score_index.py", "triage.py", "findings_rules.py", "capture_screenshots.py"}
    for path, text in _sources().items():
        if writers.search(text):
            assert path.name in allowed, f"{path.name} writes files"
    # The writers target only the dashboard cache/review roots.
    index_src = (DASHBOARD / "score_index.py").read_text()
    assert '".cache" / "dashboard"' in index_src
    assert 'scripts/.cache/dashboard_review' in (DASHBOARD / "triage.py").read_text()


def test_no_retired_v3_concepts_in_dashboard():
    retired = re.compile(r'"POOR"|"UNSAFE"|section_[a-d]_|score_bonuses|score_penalties|product_b1_penalty|'
                         r'score_100_equivalent|blob_analytics|product_catalog|filter_product_catalog|score_quality_80')
    for path, text in _sources().items():
        assert not retired.search(text), f"{path.name}: {retired.search(text).group(0)}"
