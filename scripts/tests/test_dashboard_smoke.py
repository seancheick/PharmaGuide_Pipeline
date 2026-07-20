"""Headless smoke tests: every dashboard view must render without raising.

The Streamlit dashboard is exercised against a hermetic mock provided by the
``dashboard_app`` fixture (see conftest.py), which makes the import-time
streamlit swap robust regardless of test order. These tests don't assert on
rendered output — they guard against a view crashing on real data shapes (e.g.
NULL pillar columns), so they must keep rendering all views, not skip them.
"""
import json
from pathlib import Path


def test_all_dashboard_views_smoke_render(dashboard_app):
    config = dashboard_app.DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve(),
    )
    data = dashboard_app.load_dashboard_data(config)

    views = dashboard_app.views
    view_renderers = [
        ("command-center", lambda: dashboard_app.render_command_center(data)),
        ("product-inspector", lambda: views.render_inspector(data)),
        ("pipeline-health", lambda: views.render_health(data)),
        ("data-quality", lambda: views.render_quality(data)),
        ("observability", lambda: views.render_observability(data)),
        ("release-diff", lambda: views.render_diff(data)),
        ("batch-diff", lambda: views.render_batch_diff(data)),
        ("intelligence", lambda: views.render_intelligence(data)),
        ("pillar-audit", lambda: views.render_pillar_audit(data)),
        ("suppression-audit", lambda: views.render_suppression_audit(data)),
        ("scoring-integrity", lambda: views.render_scoring_integrity(data)),
        ("module-health", lambda: views.render_module_health(data)),
    ]

    for slug, renderer in view_renderers:
        dashboard_app.render_page_frame(dashboard_app.get_page_meta(slug, data), renderer)


def test_inspector_drilldown_renders_v4_for_real_product(dashboard_app):
    """The smoke test above can't reach the Inspector drill-down (empty search
    short-circuits), so exercise it directly against a real product to cover the
    V4 six-pillar rendering path."""
    config = dashboard_app.DashboardConfig(
        scan_dir=Path("scripts/products").resolve(),
        build_root=Path("scripts/final_db_output").resolve(),
    )
    data = dashboard_app.load_dashboard_data(config)
    if data.product_catalog.empty:
        return
    dsld_id = str(data.product_catalog.iloc[0]["dsld_id"])
    dashboard_app.render_drill_down(dsld_id, data)  # must not raise


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
    metrics = data.blob_analytics["label_trust"]

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
    metrics = data.blob_analytics["label_trust"]

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

    dashboard_app.views.render_quality(data)  # must not raise


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
    metrics = data.blob_analytics["label_trust"]

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
        metrics = data.blob_analytics["label_trust"]
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
    metrics = data.blob_analytics["label_trust"]

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
    metrics = data.blob_analytics["label_trust"]

    assert set(metrics["display_dispositions"]) == set(dispositions)
    assert set(metrics["form_states"]) == set(form_states)
    assert set(metrics["identity_states"]) == set(identity_states)
    assert metrics["integrity_failures"] == 2
    assert metrics["identity_failure_products"] == 1
