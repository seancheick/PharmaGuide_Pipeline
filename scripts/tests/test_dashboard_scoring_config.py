"""The dashboard shows the production v4 scoring config and the true CAERS status.

The production scorer reads only scoring_v4/config/quality_score.json (plus the
omega rubric), stamped through scoring_v4.config_registry. The retired v3 file
scripts/config/scoring_config.json must not feed any dashboard panel, and the
CAERS page must not claim a B8 penalty that v4 never applies (retired
2026-06-24). Hermetic: empty scan/build roots and in-memory SQLite, so CI runs it.
"""
import json
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
