"""The dashboard shows the production v4 scoring config and the true CAERS status.

The production scorer reads only scoring_v4/config/quality_score.json (plus the
omega rubric), stamped through scoring_v4.config_registry. The retired v3 file
scripts/config/scoring_config.json must not feed any dashboard panel, and the
CAERS page must not claim a B8 penalty that v4 never applies (retired
2026-06-24). Hermetic: empty scan/build roots and in-memory SQLite, so CI runs it.
"""
import hashlib
import json

import pytest
import sqlite3
import types
from pathlib import Path

from scoring_v4 import config_registry
from scoring_v4.quality_score_config import config as quality_score_config

RETIRED = "scoring_config.json"


def _load_empty(dashboard_app, tmp_path):
    scan_dir, build_root = tmp_path / "scan", tmp_path / "build"
    scan_dir.mkdir()
    build_root.mkdir()
    return dashboard_app.load_dashboard_data(
        dashboard_app.DashboardConfig(scan_dir=scan_dir, build_root=build_root)
    )


def _release_db(provenances):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE products_core (dsld_id TEXT, v4_config_fingerprint TEXT)")
    conn.executemany(
        "INSERT INTO products_core VALUES (?, ?)",
        [(str(i), json.dumps(p) if p is not None else None) for i, p in enumerate(provenances)],
    )
    return conn


def _rows_by_field(rows):
    return {row["field"]: row["value"] for row in rows}


def _texts(st):
    texts = []
    for name in ("write", "info", "markdown", "caption", "error", "warning", "success"):
        for call in getattr(st, name).call_args_list:
            if call.args:
                texts.append(str(call.args[0]))
    return texts


def test_loader_snapshot_comes_from_the_v4_registry(dashboard_app, tmp_path):
    data = _load_empty(dashboard_app, tmp_path)

    assert not hasattr(data, "scoring_config"), "retired v3 config still loaded"
    snapshot = data.scoring_config_snapshot
    assert snapshot["provenance"] == config_registry.all_config_provenance()
    pillars = quality_score_config()["pillars"]
    assert snapshot["pillar_weights"] == {name: spec["weight"] for name, spec in pillars.items()}
    assert sum(snapshot["pillar_weights"].values()) == 100
    assert snapshot["release"] == []  # no release DB in an empty build root


def test_release_provenance_reads_the_scored_fingerprint_column(dashboard_app):
    loader = __import__("scripts.dashboard.data_loader", fromlist=["x"])
    current = config_registry.all_config_provenance()
    old = json.loads(json.dumps(current))
    old["quality_score"] = {"version": "1.0.0-old", "fingerprint": "0000000000000000"}

    release = loader._load_release_config_provenance(_release_db([current, current, old, None]))

    assert {json.dumps(r["provenance"], sort_keys=True): r["products"] for r in release} == {
        json.dumps(current, sort_keys=True): 2,
        json.dumps(old, sort_keys=True): 1,
        "null": 1,
    }
    no_column = sqlite3.connect(":memory:")
    no_column.execute("CREATE TABLE products_core (dsld_id TEXT)")
    assert loader._load_release_config_provenance(no_column) == []
    assert loader._load_release_config_provenance(None) == []


def test_config_snapshot_rows_show_v4_config_and_release_match(dashboard_app):
    quality = __import__("scripts.dashboard.views.quality", fromlist=["x"])
    current = config_registry.all_config_provenance()
    old = json.loads(json.dumps(current))
    old["quality_score"] = {"version": "1.0.0-old", "fingerprint": "0000000000000000"}
    snapshot = {
        "provenance": current,
        "pillar_weights": {n: s["weight"] for n, s in quality_score_config()["pillars"].items()},
    }

    def data(release):
        return types.SimpleNamespace(
            scoring_config_snapshot={**snapshot, "release": release},
            export_manifest={"scoring_version": "4.6.0"},
            shared_metrics={"average_coverage_pct": 99.0},
        )

    stale = _rows_by_field(quality.build_config_snapshot_rows(
        data([{"provenance": current, "products": 2}, {"provenance": old, "products": 3}])
    ))
    qs = current["quality_score"]
    assert stale["quality_score config (working tree)"] == f"{qs['version']} ({qs['fingerprint']})"
    assert stale["quality_score matches release"].startswith("No")
    assert stale["omega matches release"] == "Yes (5 products)"
    assert stale["Formulation max"] == "20"
    assert stale["Safety Hygiene max"] == "10"
    assert stale["Pillar total"] == "100"
    labels = " ".join(stale)
    for v3_label in ("Ingredient Quality", "Safety & Purity", "Brand Trust", "Non-GMO"):
        assert v3_label not in labels

    current_only = _rows_by_field(quality.build_config_snapshot_rows(
        data([{"provenance": current, "products": 4}])
    ))
    assert current_only["quality_score matches release"] == "Yes (4 products)"

    unknown = _rows_by_field(quality.build_config_snapshot_rows(data([])))
    assert unknown["quality_score matches release"].startswith("Unknown")


def test_caers_page_states_v4_applies_no_caers_penalty(dashboard_app, monkeypatch):
    st = dashboard_app.st
    tab_labels = []

    def tabs(labels):
        tab_labels.extend(labels)
        return [type(st)() for _ in labels]

    monkeypatch.setattr(st, "tabs", tabs)
    signals = {
        "kratom": {"signal_strength": "strong", "serious_reports": 300, "total_reports": 700,
                   "outcomes": {"death": 5}, "top_reactions": ["seizure"]},
        "calcium": {"signal_strength": "strong", "serious_reports": 2000, "total_reports": 4000,
                    "outcomes": {}, "top_reactions": ["choking"]},
        "boswellia": {"signal_strength": "weak", "serious_reports": 12, "total_reports": 30,
                      "outcomes": {}, "top_reactions": []},
    }
    data = types.SimpleNamespace(
        caers_signals=signals,
        caers_metadata={"total_supplement_reports_analyzed": 100},
    )

    dashboard_app.views.render_audit_caers(data)

    assert "Scoring Status" in tab_labels and "B8 Scoring Impact" not in tab_labels
    texts = _texts(st)
    assert any("applies no CAERS penalty" in t for t in texts)
    for false_claim in ("lose up to", "Current B8 Config", "Penalty Schedule"):
        assert not any(false_claim in t for t in texts), false_claim
    for call in st.dataframe.call_args_list:
        assert "B8 Penalty" not in getattr(call.args[0], "columns", [])


def test_page_meta_names_the_v4_config_files(dashboard_app, tmp_path):
    data = _load_empty(dashboard_app, tmp_path)

    sources = dashboard_app.get_page_meta("data-quality", data)["source_paths"]
    assert not any(path.endswith(RETIRED) for path in sources)
    registry_files = {str(p.resolve()) for p in config_registry._PROVENANCE_CONFIGS.values()}
    assert registry_files <= set(sources)

    caers = dashboard_app.get_page_meta("caers-audit", data)
    claims = " ".join([caers["page_summary"], *caers["usage_notes"]])
    assert "scoring impact" not in claims.lower()
    assert "penalties affect" not in claims
    assert "no CAERS penalty" in claims


def test_no_dashboard_module_reads_the_retired_config():
    dashboard = Path(__file__).resolve().parents[1] / "dashboard"
    readers = [
        str(path.relative_to(dashboard))
        for path in dashboard.rglob("*.py")
        if f"config/{RETIRED}" in path.read_text()
    ]
    assert readers == []


def test_config_snapshot_reloads_current_files_without_mutating_scorer_cache(
    dashboard_app, tmp_path, monkeypatch
):
    loader = __import__("scripts.dashboard.data_loader", fromlist=["x"])
    registry = __import__("scripts.scoring_v4.config_registry", fromlist=["x"])
    quality = __import__("scripts.scoring_v4.quality_score_config", fromlist=["x"])
    original_provenance = registry.all_config_provenance()
    original_config = quality.config()
    paths = {}
    for name, source in registry._PROVENANCE_CONFIGS.items():
        path = tmp_path / source.name
        path.write_bytes(source.read_bytes())
        paths[name] = path
    monkeypatch.setattr(registry, "_PROVENANCE_CONFIGS", paths)
    monkeypatch.setattr(quality, "_PATH", paths["quality_score"])
    release = _release_db([original_provenance])
    assert loader._load_scoring_config_snapshot(release, [])["provenance"] == original_provenance

    for name, path in paths.items():
        payload = json.loads(path.read_bytes())
        payload["_metadata"]["version"] = "test-updated"
        if name == "quality_score":
            payload["pillars"]["formulation"]["weight"] = 19
            payload["pillars"]["dose"]["weight"] = 21
        path.write_text(json.dumps(payload))
    # Both Refresh and expiry re-enter the loader body. Streamlit is a pass-through
    # fixture here; no cache invalidation on the scorer is permitted in either case.
    warnings = []
    snapshot = loader._load_scoring_config_snapshot(release, warnings)
    assert warnings == []
    for name, path in paths.items():
        assert snapshot["provenance"][name] == {
            "version": "test-updated",
            "fingerprint": hashlib.sha256(path.read_bytes()).hexdigest()[:16],
        }
    assert snapshot["pillar_weights"]["formulation"] == 19
    assert snapshot["pillar_weights"]["dose"] == 21
    quality_view = __import__("scripts.dashboard.views.quality", fromlist=["x"])
    rows = _rows_by_field(quality_view.build_config_snapshot_rows(types.SimpleNamespace(
        scoring_config_snapshot=snapshot, export_manifest={}, shared_metrics={}
    )))
    assert rows["quality_score matches release"].startswith("No")
    assert rows["omega matches release"].startswith("No")
    assert registry.all_config_provenance() == original_provenance
    assert quality.config() is original_config


@pytest.mark.parametrize("failure", ["missing", "malformed", "non_object", "pillars_list", "pillars_null", "pillars_empty", "weight_string", "weight_null", "weight_bool", "weight_nonfinite"])
def test_config_snapshot_reports_invalid_file_after_cached_success(
    dashboard_app, tmp_path, monkeypatch, failure
):
    loader = __import__("scripts.dashboard.data_loader", fromlist=["x"])
    registry = __import__("scripts.scoring_v4.config_registry", fromlist=["x"])
    quality = __import__("scripts.scoring_v4.quality_score_config", fromlist=["x"])
    registry.all_config_provenance()
    quality.config()
    path = tmp_path / "quality_score.json"
    path.write_bytes(registry._PROVENANCE_CONFIGS["quality_score"].read_bytes())
    monkeypatch.setattr(registry, "_PROVENANCE_CONFIGS", {
        **registry._PROVENANCE_CONFIGS, "quality_score": path,
    })
    monkeypatch.setattr(quality, "_PATH", path)
    assert loader._load_scoring_config_snapshot(None, [])["pillar_weights"]
    if failure == "missing":
        path.unlink()
    elif failure.startswith("weight_"):
        payload = json.loads(path.read_bytes())
        payload["pillars"]["formulation"]["weight"] = {"weight_string": "20", "weight_null": None, "weight_bool": True, "weight_nonfinite": float("nan")}[failure]
        path.write_text(json.dumps(payload))
    elif failure.startswith("pillars_"):
        payload = json.loads(path.read_bytes())
        payload["pillars"] = {"pillars_list": [], "pillars_null": None, "pillars_empty": {}}[failure]
        path.write_text(json.dumps(payload))
    else:
        path.write_text("{" if failure == "malformed" else "[]")
    warnings = []
    assert loader._load_scoring_config_snapshot(None, warnings) == {}
    assert len(warnings) == 1
    assert warnings[0].startswith("v4 scoring config could not be read:")


@pytest.mark.parametrize("invalid", [[1], [], "bad", "", 1, 0, True, False, None])
def test_release_provenance_non_objects_are_unknown_and_preserve_product_counts(
    dashboard_app, invalid
):
    loader = __import__("scripts.dashboard.data_loader", fromlist=["x"])
    quality_view = __import__("scripts.dashboard.views.quality", fromlist=["x"])
    current = config_registry.all_config_provenance()
    release = loader._load_release_config_provenance(_release_db([current, invalid, invalid]))
    assert sum(row["products"] for row in release) == 3
    assert sum(row["products"] for row in release if row["provenance"] is None) == 2
    rows = _rows_by_field(quality_view.build_config_snapshot_rows(types.SimpleNamespace(
        scoring_config_snapshot={"provenance": current, "pillar_weights": {}, "release": release},
        export_manifest={}, shared_metrics={}
    )))
    assert rows["quality_score matches release"] == "No (1 of 3 products match)"
    assert "not recorded" in rows["quality_score config (release)"]
