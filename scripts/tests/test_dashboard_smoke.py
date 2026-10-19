"""Headless smoke tests: every dashboard view must render without raising.

The Streamlit dashboard is exercised against a hermetic mock provided by the
``dashboard_app`` fixture (see conftest.py), which makes the import-time
streamlit swap robust regardless of test order. These tests don't assert on
rendered output — they guard against a view crashing on real data shapes (e.g.
NULL pillar columns), so they must keep rendering all views, not skip them.
"""
import json
from pathlib import Path

import pytest

from scripts.release_artifact_paths import final_build_dir


def test_all_dashboard_pages_smoke_render(dashboard_app):
    """Every page renders against the real local artifacts and index (or its absence)."""
    config = dashboard_app.DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=final_build_dir(),
    )
    data = dashboard_app.load_dashboard_data(config)
    ctx = dashboard_app.shell.init(data)
    for spec in dashboard_app.navigation.PAGES:
        module = dashboard_app.view(spec.module)
        dashboard_app.render_page_frame(dashboard_app.get_page_meta(spec.slug, data), lambda: module.render(ctx))


def test_product_trace_renders_a_real_product(dashboard_app):
    """Exercise the trace path (ledgers, waterfall, gates) on a real indexed product."""
    config = dashboard_app.DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=final_build_dir(),
    )
    data = dashboard_app.load_dashboard_data(config)
    ctx = dashboard_app.shell.init(data)
    if not ctx.ready:
        return
    dsld_id = str(ctx.products().iloc[0]["dsld_id"])
    dashboard_app.st.session_state["trace_dsld_id"] = dsld_id
    dashboard_app.view("trace").render(ctx)  # must not raise


def _label_trust(dashboard_app, build_root):
    """Release label-trust metrics from blobs, through the index projection the dashboard uses."""
    import importlib

    loader = importlib.import_module("scripts.dashboard.data_loader")
    score_index = importlib.import_module("scripts.dashboard.score_index")
    blob_dir = build_root / "detail_blobs"
    records = []
    for path in sorted(blob_dir.glob("*.json")) if blob_dir.exists() else []:
        blob = loader.safe_load_json(path)
        if blob:
            records.append(score_index.label_trust_record(blob, {"dsld_id": path.stem}))
    return loader.compute_label_trust(records, build_root / "label_mismatch_summary.json")


def test_label_trust_dashboard_aggregates_only_release_safe_metrics(
    dashboard_app, tmp_path
):
    build_root = tmp_path / "build"
    blob_dir = build_root / "detail_blobs"
    blob_dir.mkdir(parents=True)
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()

    blobs = [
        {
            "dsld_id": "one",
            "brand_name": "Brand A",
            "primary_type": "omega_3",
            "label_ledger_audit": {
                "support_status": "supported",
                "completeness_status": "complete",
                "completeness_percentage": 100.0,
            },
            "display_ingredients": [
                {
                    "display_disposition": "scored",
                    "form_display_state": "assessed",
                    "identity_integrity_state": "clean",
                },
                {
                    "display_disposition": "label_context",
                    "form_display_state": "listed_not_assessed",
                    "identity_integrity_state": "taxonomy_only",
                },
                {
                    "display_disposition": "needs_review",
                    "form_display_state": "needs_review",
                    "identity_integrity_state": "identity_conflict",
                },
            ],
            "label_record": {
                "history_status": "available",
                "formula_history": [{"snapshot_id": "older"}],
            },
        },
        {
            "dsld_id": "two",
            "brand_name": "Brand B",
            "primary_type": "multivitamin",
            "label_ledger_audit": {
                "support_status": "supported",
                "completeness_status": "incomplete",
                "completeness_percentage": 75.0,
            },
            "display_ingredients": [
                {
                    "display_disposition": "scored",
                    "form_display_state": "not_disclosed",
                    "identity_integrity_state": "repaired",
                }
            ],
            "label_record": {
                "history_status": "unavailable",
                "formula_history": [],
            },
        },
    ]
    for blob in blobs:
        (blob_dir / f"{blob['dsld_id']}.json").write_text(json.dumps(blob))

    (build_root / "label_mismatch_summary.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "outcomes": [
                    {"status": "submitted", "count": 3},
                    {"status": "resolved", "count": 2},
                    {"status": "not_allowed", "count": 99},
                ],
                "categories": [
                    {"category": "ingredient_missing", "count": 2},
                    {"category": "amount_or_unit", "count": 1},
                    {"category": "free text from user", "count": 99},
                ],
            }
        )
    )

    data = dashboard_app.load_dashboard_data(
        dashboard_app.DashboardConfig(scan_dir=scan_dir, build_root=build_root)
    )
    metrics = data.label_trust = _label_trust(dashboard_app, build_root)

    assert metrics["total_products"] == 2
    assert metrics["supported_products"] == 2
    assert metrics["unsupported_products"] == 0
    assert metrics["complete_products"] == 1
    assert metrics["incomplete_products"] == 1
    assert metrics["average_completeness_pct"] == 87.5
    assert metrics["invalid_audit_products"] == 0
    assert metrics["display_dispositions"] == {
        "label_context": 1,
        "needs_review": 1,
        "scored": 2,
    }
    assert metrics["form_states"] == {
        "assessed": 1,
        "listed_not_assessed": 1,
        "needs_review": 1,
        "not_disclosed": 1,
    }
    assert metrics["integrity_failures"] == 1
    assert metrics["identity_failure_products"] == 1
    assert metrics["total_display_rows"] == 4
    assert metrics["unrecognized_display_dispositions"] == 0
    assert metrics["unrecognized_form_states"] == 0
    assert metrics["unrecognized_identity_states"] == 0
    assert metrics["formula_history_products"] == 1
    assert metrics["formula_history_coverage_pct"] == 50.0
    assert metrics["mismatch_outcomes"] == {"resolved": 2, "submitted": 3}
    assert metrics["mismatch_categories"] == {
        "amount_or_unit": 1,
        "ingredient_missing": 2,
    }
    assert metrics["rejected_mismatch_outcomes"] == 1
    assert metrics["rejected_mismatch_categories"] == 1
    assert metrics["invalid_mismatch_summary"] == 0
    assert {row["brand_name"] for row in metrics["by_brand"]} == {
        "Brand A",
        "Brand B",
    }
    assert {row["primary_type"] for row in metrics["by_category"]} == {
        "multivitamin",
        "omega_3",
    }
    serialized = json.dumps(metrics)
    assert "free text from user" not in serialized


def test_label_trust_dashboard_zero_rows_are_explicit_and_renderable(
    dashboard_app, tmp_path
):
    build_root = tmp_path / "build"
    build_root.mkdir()
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()

    data = dashboard_app.load_dashboard_data(
        dashboard_app.DashboardConfig(scan_dir=scan_dir, build_root=build_root)
    )
    metrics = data.label_trust = _label_trust(dashboard_app, build_root)

    assert metrics == {
        "total_products": 0,
        "supported_products": 0,
        "unsupported_products": 0,
        "complete_products": 0,
        "incomplete_products": 0,
        "unavailable_products": 0,
        "invalid_audit_products": 0,
        "average_completeness_pct": None,
        "display_dispositions": {},
        "form_states": {},
        "identity_states": {},
        "integrity_failures": 0,
        "identity_failure_products": 0,
        "total_display_rows": 0,
        "unrecognized_display_dispositions": 0,
        "unrecognized_form_states": 0,
        "unrecognized_identity_states": 0,
        "formula_history_products": 0,
        "formula_history_coverage_pct": None,
        "mismatch_outcomes": {},
        "mismatch_categories": {},
        "rejected_mismatch_outcomes": 0,
        "rejected_mismatch_categories": 0,
        "invalid_mismatch_summary": 0,
        "by_brand": [],
        "by_category": [],
    }

    dashboard_app.view("quality").render_quality(data)  # must not raise


def test_label_trust_dashboard_surfaces_invalid_contracts_without_raw_values(
    dashboard_app, tmp_path
):
    build_root = tmp_path / "build"
    blob_dir = build_root / "detail_blobs"
    blob_dir.mkdir(parents=True)
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    (blob_dir / "invalid.json").write_text(
        json.dumps(
            {
                "brand_name": "Brand A",
                "primary_type": "omega_3",
                "label_ledger_audit": {
                    "support_status": "unsupported",
                    "completeness_status": "unavailable",
                    "completeness_percentage": 100.0,
                },
                "display_ingredients": [
                    {
                        "display_disposition": "future-private-disposition",
                        "form_display_state": "raw user form text",
                        "identity_integrity_state": "new identity value",
                    },
                    {
                        "display_disposition": ["private", "value"],
                        "form_display_state": {"raw": "form"},
                        "identity_integrity_state": ["raw", "identity"],
                    }
                ],
                "label_record": {
                    "history_status": "available",
                    "formula_history": [],
                },
            }
        )
    )
    (blob_dir / "unsupported.json").write_text(
        json.dumps(
            {
                "brand_name": "Brand A",
                "primary_type": "omega_3",
                "label_ledger_audit": {
                    "support_status": "unsupported",
                    "completeness_status": "unavailable",
                    "completeness_percentage": None,
                },
            }
        )
    )
    (build_root / "label_mismatch_summary.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "outcomes": [
                    {
                        "status": "submitted",
                        "count": 1,
                        "photo_path": "private/report/front",
                    }
                ],
                "categories": [
                    {
                        "category": "ingredient_missing",
                        "count": 1,
                        "user_id": "private-user",
                    }
                ],
            }
        )
    )

    data = dashboard_app.load_dashboard_data(
        dashboard_app.DashboardConfig(scan_dir=scan_dir, build_root=build_root)
    )
    metrics = data.label_trust = _label_trust(dashboard_app, build_root)

    assert metrics["invalid_audit_products"] == 1
    assert metrics["supported_products"] == 0
    assert metrics["unsupported_products"] == 1
    assert metrics["complete_products"] == 0
    assert metrics["incomplete_products"] == 0
    assert metrics["unavailable_products"] == 1
    assert metrics["average_completeness_pct"] is None
    assert metrics["unrecognized_display_dispositions"] == 2
    assert metrics["unrecognized_form_states"] == 2
    assert metrics["unrecognized_identity_states"] == 2
    assert metrics["integrity_failures"] == 2
    assert metrics["identity_failure_products"] == 1
    assert metrics["mismatch_outcomes"] == {}
    assert metrics["mismatch_categories"] == {}
    assert metrics["rejected_mismatch_outcomes"] == 1
    assert metrics["rejected_mismatch_categories"] == 1
    assert metrics["invalid_mismatch_summary"] == 0
    brand_row = metrics["by_brand"][0]
    assert brand_row["supported_products"] == 0
    assert brand_row["unsupported_products"] == 1
    assert brand_row["invalid_audit_products"] == 1
    assert brand_row["complete_products"] == 0
    assert brand_row["incomplete_products"] == 0
    assert brand_row["unavailable_products"] == 1
    serialized = json.dumps(metrics)
    assert "future-private-disposition" not in serialized
    assert "raw user form text" not in serialized
    assert "new identity value" not in serialized
    assert "private/report/front" not in serialized
    assert "private-user" not in serialized


def test_label_trust_dashboard_rejects_invalid_mismatch_summary_schema(
    dashboard_app, tmp_path
):
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    invalid_summaries = [
        {
            "schema_version": True,
            "outcomes": [],
            "categories": [],
        },
        {
            "schema_version": 1.0,
            "outcomes": [],
            "categories": [],
        },
        {"schema_version": 1, "outcomes": []},
        {
            "schema_version": 2,
            "outcomes": [],
            "categories": [],
        },
        {
            "schema_version": 1,
            "outcomes": [],
            "categories": [],
            "user_id": "must-never-appear",
        },
    ]

    for index, summary in enumerate(invalid_summaries):
        build_root = tmp_path / f"build-{index}"
        build_root.mkdir()
        (build_root / "label_mismatch_summary.json").write_text(
            json.dumps(summary)
        )
        data = dashboard_app.load_dashboard_data(
            dashboard_app.DashboardConfig(
                scan_dir=scan_dir,
                build_root=build_root,
            )
        )
        metrics = data.label_trust = _label_trust(dashboard_app, build_root)
        assert metrics["invalid_mismatch_summary"] == 1
        assert metrics["mismatch_outcomes"] == {}
        assert metrics["mismatch_categories"] == {}
        assert "must-never-appear" not in json.dumps(metrics)


def test_label_trust_dashboard_rejects_unhashable_mismatch_values(
    dashboard_app, tmp_path
):
    build_root = tmp_path / "build"
    build_root.mkdir()
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    (build_root / "label_mismatch_summary.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "outcomes": [{"status": ["submitted"], "count": 1}],
                "categories": [
                    {"category": {"raw": "ingredient_missing"}, "count": 1}
                ],
            }
        )
    )

    data = dashboard_app.load_dashboard_data(
        dashboard_app.DashboardConfig(scan_dir=scan_dir, build_root=build_root)
    )
    metrics = data.label_trust = _label_trust(dashboard_app, build_root)

    assert metrics["invalid_mismatch_summary"] == 0
    assert metrics["mismatch_outcomes"] == {}
    assert metrics["mismatch_categories"] == {}
    assert metrics["rejected_mismatch_outcomes"] == 1
    assert metrics["rejected_mismatch_categories"] == 1


def test_label_trust_dashboard_counts_every_closed_state(dashboard_app, tmp_path):
    build_root = tmp_path / "build"
    blob_dir = build_root / "detail_blobs"
    blob_dir.mkdir(parents=True)
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    dispositions = ["scored", "label_context", "other_ingredient", "needs_review"]
    form_states = [
        "assessed",
        "not_disclosed",
        "listed_not_assessed",
        "not_applicable",
        "needs_review",
    ]
    identity_states = [
        "clean",
        "repaired",
        "taxonomy_only",
        "identity_conflict",
        "missing_display_label",
    ]
    rows = [
        {
            "display_disposition": dispositions[index % len(dispositions)],
            "form_display_state": form_states[index],
            "identity_integrity_state": identity_states[index],
        }
        for index in range(len(form_states))
    ]
    (blob_dir / "states.json").write_text(
        json.dumps(
            {
                "label_ledger_audit": {
                    "support_status": "supported",
                    "completeness_status": "complete",
                    "completeness_percentage": 100.0,
                },
                "display_ingredients": rows,
            }
        )
    )

    data = dashboard_app.load_dashboard_data(
        dashboard_app.DashboardConfig(scan_dir=scan_dir, build_root=build_root)
    )
    metrics = data.label_trust = _label_trust(dashboard_app, build_root)

    assert set(metrics["display_dispositions"]) == set(dispositions)
    assert set(metrics["form_states"]) == set(form_states)
    assert set(metrics["identity_states"]) == set(identity_states)
    assert metrics["integrity_failures"] == 2
    assert metrics["identity_failure_products"] == 1


def test_safety_copy_depletion_summary_reads_the_real_file_key(dashboard_app):
    """The depletion file's list lives under ``depletions``; reading any other
    key silently reported 0 entries on the safety-copy dashboard."""
    import importlib

    safety_copy = importlib.import_module("scripts.dashboard.views.safety_copy")
    data = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "medication_depletions.json").read_text()
    )
    summary = safety_copy._depletions_summary(data)
    assert summary["total"] == data["_metadata"]["total_entries"] > 0


def _empty_roots(tmp_path):
    scan_dir = tmp_path / "scan"
    build_root = tmp_path / "build"
    scan_dir.mkdir()
    build_root.mkdir()
    return scan_dir, build_root


def _pipeline_schema(name):
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / name).read_text())
    return data["_metadata"]["schema_version"]


def _messages(widget):
    return [str(call.args[0]) for call in widget.call_args_list]


def _flutter_sync_tables(st):
    """The Clinical Copy view renders exactly one table with a ``flutter`` column."""
    return [
        call.args[0]
        for call in st.dataframe.call_args_list
        if "flutter" in getattr(call.args[0], "columns", [])
    ]


def test_dashboard_config_resolves_flutter_repo_from_env_then_flag(
    dashboard_app, monkeypatch, tmp_path
):
    """The dashboard finds the app checkout the way the release scripts do:
    FLUTTER_REPO, overridden by --flutter-repo, and no personal-path default."""
    import importlib
    import sys

    get_config = importlib.import_module("scripts.dashboard.config").get_config
    monkeypatch.setattr(sys, "argv", ["app.py"])
    monkeypatch.delenv("FLUTTER_REPO", raising=False)
    assert get_config().flutter_repo is None

    monkeypatch.setenv("FLUTTER_REPO", str(tmp_path / "from_env"))
    assert get_config().flutter_repo == (tmp_path / "from_env").resolve()

    monkeypatch.setattr(
        sys, "argv", ["app.py", "--flutter-repo", str(tmp_path / "from_flag")]
    )
    assert get_config().flutter_repo == (tmp_path / "from_flag").resolve()


def test_safety_copy_without_flutter_repo_reports_assets_not_configured(
    dashboard_app, tmp_path
):
    scan_dir, build_root = _empty_roots(tmp_path)
    data = dashboard_app.load_dashboard_data(
        dashboard_app.DashboardConfig(scan_dir=scan_dir, build_root=build_root)
    )
    assert data.flutter_repo is None
    st = dashboard_app.st

    dashboard_app.view("safety_copy").render_safety_copy(data)

    assert any("Flutter assets not configured" in m for m in _messages(st.info))
    assert _flutter_sync_tables(st) == []
    assert not any("Flutter assets in sync" in m for m in _messages(st.success))


def test_safety_copy_with_missing_flutter_assets_reports_unavailable(
    dashboard_app, tmp_path
):
    scan_dir, build_root = _empty_roots(tmp_path)
    absent = tmp_path / "absent_app"
    data = dashboard_app.load_dashboard_data(
        dashboard_app.DashboardConfig(
            scan_dir=scan_dir, build_root=build_root, flutter_repo=absent
        )
    )
    st = dashboard_app.st

    dashboard_app.view("safety_copy").render_safety_copy(data)

    unavailable = [m for m in _messages(st.warning) if "Flutter assets unavailable" in m]
    assert unavailable and str(absent / "assets" / "reference_data") in unavailable[0]
    assert _flutter_sync_tables(st) == []
    assert not any("Flutter assets in sync" in m for m in _messages(st.success))


def test_safety_copy_with_flutter_repo_compares_asset_schema_versions(
    dashboard_app, tmp_path
):
    scan_dir, build_root = _empty_roots(tmp_path)
    flutter = tmp_path / "app"
    assets = flutter / "assets" / "reference_data"
    assets.mkdir(parents=True)
    (assets / "medication_depletions.json").write_text(
        json.dumps({"_metadata": {"schema_version": _pipeline_schema("medication_depletions.json")}})
    )
    (assets / "banned_recalled_ingredients.json").write_text(
        json.dumps({"_metadata": {"schema_version": "0.0.0-stale"}})
    )
    data = dashboard_app.load_dashboard_data(
        dashboard_app.DashboardConfig(
            scan_dir=scan_dir, build_root=build_root, flutter_repo=flutter
        )
    )
    assert data.flutter_repo == flutter
    st = dashboard_app.st

    dashboard_app.view("safety_copy").render_safety_copy(data)

    (table,) = _flutter_sync_tables(st)
    rows = table.set_index("file")
    assert rows.loc["medication_depletions.json", "status"] == "✅ schema matches"
    assert rows.loc["banned_recalled_ingredients.json", "status"] == "⚠️ stale"
    assert rows.loc["synergy_cluster.json", "status"] == "⚠️ unavailable"
    assert any(
        "Flutter sync stale: banned_recalled_ingredients.json" in m
        for m in _messages(st.warning)
    )
    assert not any("Flutter assets" in m for m in _messages(st.info))


@pytest.mark.parametrize("defect", ["empty", "missing", "malformed", "unreadable", "wrong_shape", "missing_schema", "invalid_metadata", "empty_schema"])
def test_safety_copy_expected_flutter_assets_cannot_report_success(
    dashboard_app, tmp_path, monkeypatch, defect
):
    scan_dir, build_root = _empty_roots(tmp_path)
    flutter = tmp_path / "app"
    assets = flutter / "assets" / "reference_data"
    assets.mkdir(parents=True)
    expected = ("medication_depletions.json", "banned_recalled_ingredients.json", "synergy_cluster.json")
    if defect != "empty":
        for name in expected:
            (assets / name).write_text(json.dumps({"_metadata": {"schema_version": _pipeline_schema(name)}}))
        target = assets / "synergy_cluster.json"
        if defect == "missing":
            target.unlink()
        elif defect == "malformed":
            target.write_text("{broken")
        elif defect == "wrong_shape":
            target.write_text("[]")
        elif defect == "missing_schema":
            target.write_text('{"_metadata": {}}')
        elif defect == "invalid_metadata":
            target.write_text('{"_metadata": []}')
        elif defect == "empty_schema":
            target.write_text('{"_metadata": {"schema_version": " "}}')
        elif defect == "unreadable":
            original = Path.read_text
            def read_text(path, *args, **kwargs):
                if path == target:
                    raise PermissionError("denied")
                return original(path, *args, **kwargs)
            monkeypatch.setattr(Path, "read_text", read_text)
    data = dashboard_app.load_dashboard_data(dashboard_app.DashboardConfig(
        scan_dir=scan_dir, build_root=build_root, flutter_repo=flutter
    ))
    dashboard_app.view("safety_copy").render_safety_copy(data)
    (table,) = _flutter_sync_tables(dashboard_app.st)
    rows = table.set_index("file")
    assert rows.loc["synergy_cluster.json", "status"] == "⚠️ unavailable"
    if defect == "empty":
        assert all(rows.loc[name, "status"] == "⚠️ unavailable" for name in expected)
    assert any("Flutter schema check unavailable: synergy_cluster.json" in m for m in _messages(dashboard_app.st.warning))
    assert not any("schema versions match" in m or "Flutter assets in sync" in m for m in _messages(dashboard_app.st.success))


def test_safety_copy_checks_expected_assets_and_excludes_unbundled_sources(dashboard_app, tmp_path):
    scan_dir, build_root = _empty_roots(tmp_path)
    flutter = tmp_path / "app"
    assets = flutter / "assets" / "reference_data"
    assets.mkdir(parents=True)
    for name in ("medication_depletions.json", "banned_recalled_ingredients.json", "synergy_cluster.json"):
        (assets / name).write_text(json.dumps({"_metadata": {"schema_version": _pipeline_schema(name)}}))
    data = dashboard_app.load_dashboard_data(dashboard_app.DashboardConfig(
        scan_dir=scan_dir, build_root=build_root, flutter_repo=flutter
    ))
    dashboard_app.view("safety_copy").render_safety_copy(data)
    (table,) = _flutter_sync_tables(dashboard_app.st)
    rows = table.set_index("file")
    for name in ("medication_depletions.json", "banned_recalled_ingredients.json", "synergy_cluster.json"):
        assert rows.loc[name, "status"] == "✅ schema matches"
    for name in ("ingredient_interaction_rules.json", "harmful_additives.json", "manufacturer_violations.json"):
        assert rows.loc[name, "flutter"] == "not bundled"
    assert not any("Flutter assets in sync" in m for m in _messages(dashboard_app.st.success))
    assert not any("Flutter schema check unavailable" in m for m in _messages(dashboard_app.st.warning))
