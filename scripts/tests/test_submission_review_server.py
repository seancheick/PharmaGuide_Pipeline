"""Reviewer console server contract (scripts/submission_review/serve.py).

Pins the security shape of the local tool: loopback-only bind, a single
allowed proxy target (the deployed review Edge Function — never a
caller-chosen URL), parameterized catalog search, and the vendored
supabase-js bundle (pinned version, recorded checksum — no runtime CDN).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REVIEW_DIR = SCRIPTS_DIR / "submission_review"
sys.path.insert(0, str(REVIEW_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import serve  # noqa: E402

VENDORED_SUPABASE_JS = REVIEW_DIR / "static" / "vendor" / "supabase.js"
VENDORED_SUPABASE_SHA256 = (
    "2697f51bb3efa5f10b5b0bca2a39b3772b1b8f810e6885e3bb8d69c3242d5e07"
)
GTIN_FIXTURE = REVIEW_DIR / "fixtures" / "gtin_golden.json"
GTIN_FIXTURE_SHA256 = (
    "d96e600c74654f813da95246ef1d027c042ba62eac7eb05675bcdf58c728f4dc"
)


def test_server_binds_loopback_only():
    assert serve.BIND_HOST == "127.0.0.1"
    source = (REVIEW_DIR / "serve.py").read_text()
    assert "0.0.0.0" not in source


def test_static_reviewer_assets_are_never_served_from_stale_cache():
    server = ThreadingHTTPServer((serve.BIND_HOST, 0), serve.ReviewerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://{serve.BIND_HOST}:{server.server_port}/app.js"
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.headers["cache-control"] == "no-store"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_reviewer_page_busts_pre_no_store_asset_caches():
    index_html = (REVIEW_DIR / "static" / "index.html").read_text()

    for asset in ("styles.css", "canonical.js", "app.js"):
        assert f'/{asset}?v=20260903-1' in index_html


def test_proxy_targets_exactly_the_review_function():
    url = serve.edge_function_url("https://example.supabase.co/")
    assert url == (
        "https://example.supabase.co"
        "/functions/v1/review-product-submissions"
    )
    # The handler builds its target from this constant alone; no request
    # field may choose a different host or path.
    source = (REVIEW_DIR / "serve.py").read_text()
    assert source.count("urllib.request.Request(") == 1
    assert "edge_function_url(self.supabase_url)" in source


def test_photo_proxy_only_allows_this_projects_private_submission_photos():
    project = "https://example.supabase.co"
    valid = (
        "https://example.supabase.co/storage/v1/object/sign/"
        "product-submission-photos/user/submission/photo?token=secret"
    )
    assert serve.validate_submission_photo_url(valid, project) == valid

    forbidden = (
        "https://evil.example/storage/v1/object/sign/"
        "product-submission-photos/user/submission/photo?token=secret",
        "http://example.supabase.co/storage/v1/object/sign/"
        "product-submission-photos/user/submission/photo?token=secret",
        "https://example.supabase.co/storage/v1/object/public/"
        "product-submission-photos/user/submission/photo",
        "https://example.supabase.co/storage/v1/object/sign/other-bucket/"
        "user/submission/photo?token=secret",
        "https://example.supabase.co/storage/v1/object/sign/"
        "product-submission-photos/user/submission/photo",
    )
    for url in forbidden:
        with pytest.raises(ValueError):
            serve.validate_submission_photo_url(url, project)


def test_lightbox_fetches_private_photo_through_same_origin_proxy():
    app_js = (REVIEW_DIR / "static" / "app.js").read_text()

    assert "async function fetchReviewPhoto(signedUrl)" in app_js
    assert "fetch('/api/photo'" in app_js
    assert "signed_url: signedUrl" in app_js
    assert "authorization: `Bearer ${state.session.access_token}`" in app_js
    assert "fetch(photo.signed_url)" not in app_js


def test_selecting_another_submission_resets_image_inputs():
    app_js = (REVIEW_DIR / "static" / "app.js").read_text()

    select_body = app_js.split("function select(submission) {", 1)[1].split(
        "\n}", 1
    )[0]
    assert "$('reviewer-image-attestation').checked = false;" in select_body
    assert "$('reviewer-image-file').value = '';" in select_body


def test_catalog_search_is_parameterized_and_bounded(tmp_path):
    db = tmp_path / "catalog.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "create table products_core "
            "(dsld_id text primary key, product_name text, brand_name text, "
            "upc_sku text)"
        )
        conn.executemany(
            "insert into products_core values (?, ?, ?, ?)",
            [
                ("278454", "Vitamin D3", "Example Labs", "016000275447"),
                ("PG_SUB_AA", "Ashwagandha + GABA", "Youtheory", "96385074"),
                # SQL-injection-shaped name must be inert data.
                ("666", "x'; DROP TABLE products_core;--", "Evil", ""),
            ],
        )

    by_name = serve.search_catalog(db, "Vitamin")
    assert [row["dsld_id"] for row in by_name] == ["278454"]

    by_upc = serve.search_catalog(db, "0 16000 27544 7")
    assert [row["dsld_id"] for row in by_upc] == ["278454"]

    by_id = serve.search_catalog(db, "PG_SUB_AA")
    assert [row["dsld_id"] for row in by_id] == ["PG_SUB_AA"]

    injected = serve.search_catalog(db, "'; DROP TABLE products_core;--")
    assert [row["dsld_id"] for row in injected] == ["666"]
    # Table still exists — the quote traveled as data.
    assert serve.search_catalog(db, "Vitamin")

    assert serve.search_catalog(db, "") == []


def test_vendored_supabase_js_is_pinned_by_checksum():
    assert VENDORED_SUPABASE_JS.exists(), (
        "The reviewer page must ship its supabase-js bundle; "
        "runtime CDN loads are forbidden."
    )
    digest = hashlib.sha256(VENDORED_SUPABASE_JS.read_bytes()).hexdigest()
    assert digest == VENDORED_SUPABASE_SHA256, (
        "vendored supabase.js changed; review the diff and update the "
        "pinned checksum deliberately"
    )
    index_html = (REVIEW_DIR / "static" / "index.html").read_text()
    assert '"/vendor/supabase.js"' in index_html
    for forbidden in ("esm.sh", "cdn.jsdelivr.net", "unpkg.com"):
        assert forbidden not in index_html


def test_static_page_never_embeds_service_credentials():
    for asset in (REVIEW_DIR / "static").glob("*.js"):
        text = asset.read_text()
        assert "sb_secret" not in text
        assert "SERVICE_ROLE" not in text


def test_console_defaults_to_open_queue_and_supports_cursor_pagination():
    index_html = (REVIEW_DIR / "static" / "index.html").read_text()
    app_js = (REVIEW_DIR / "static" / "app.js").read_text()

    assert '<option value="open" selected>Open</option>' in index_html
    assert 'id="queue-count"' in index_html
    assert 'id="load-more"' in index_html
    assert "body.after = state.nextAfter" in app_js
    assert "state.submissions.push(...submissions)" in app_js
    assert "total_open_count" in app_js
    assert "next_after" in app_js


def test_identity_index_gtin_semantics_are_fixture_pinned():
    assert hashlib.sha256(GTIN_FIXTURE.read_bytes()).hexdigest() == (
        GTIN_FIXTURE_SHA256
    )
    fixture = json.loads(GTIN_FIXTURE.read_text())
    for vector in fixture["valid_identities"]:
        assert vector["canonical_gtin14"] in serve.canonical_gtin14_candidates(
            vector["input"]
        )
    for vector in fixture["manual_eight_digit"]:
        expected = {
            candidate.rjust(14, "0")
            for candidate in vector["lookup_candidates"]
            if len(candidate) in {8, 12, 13, 14}
        }
        assert expected.intersection(
            serve.canonical_gtin14_candidates(vector["input"])
        )
    for vector in fixture["invalid_inputs"]:
        assert not serve.canonical_gtin14_candidates(vector["input"])


def test_identity_index_combines_catalog_and_manifest_owned_corpus(tmp_path):
    catalog = tmp_path / "catalog.db"
    with sqlite3.connect(catalog) as conn:
        conn.execute(
            "create table products_core "
            "(dsld_id text primary key, product_name text, brand_name text, "
            "upc_sku text)"
        )
        conn.execute(
            "insert into products_core values (?, ?, ?, ?)",
            ("278454", "Vitamin D3", "Example Labs", "050428381397"),
        )

    stage = tmp_path / "products" / "output_Test_enriched" / "enriched"
    stage.mkdir(parents=True)
    batch = stage / "enriched_cleaned_batch_1.json"
    batch.write_text(
        json.dumps(
            [
                {
                    "dsldId": 278454,
                    "fullName": "Vitamin D3",
                    "brandName": "Example Labs",
                    "upcSku": "050428381397",
                },
                {
                    "dsldId": 900001,
                    "fullName": "Corpus only",
                    "brandName": "New Labs",
                    "upcSku": "4006381333931",
                    "ingredientRows": [
                        {
                            "ingredientGroup": "Vitamin D",
                            "name": "Vitamin D3",
                            "quantity": [{"quantity": 25, "unit": "mcg"}],
                            "forms": [{"name": "Cholecalciferol"}],
                            "nestedRows": [],
                            "safety_hits": [{"rule": "server-only"}],
                        }
                    ],
                    "row_ledger": [{"disposition": "server-only"}],
                },
                {
                    "dsldId": 900002,
                    "fullName": "Second exact version",
                    "brandName": "New Labs",
                    "upcSku": "4006381333931",
                },
            ]
        )
    )
    manifest = {
        "schema_version": "1.0.0",
        "stage": "enrich",
        "processing_complete": True,
        "owned_files": [batch.name],
        "content_sha256": {
            batch.name: hashlib.sha256(batch.read_bytes()).hexdigest()
        },
    }
    (stage / ".stage_manifest.json").write_text(json.dumps(manifest))

    built_at = datetime(2026, 8, 25, 18, 0, tzinfo=timezone.utc)
    index = serve.build_identity_index(
        catalog,
        tmp_path / "products",
        built_at=built_at,
    )

    shipped = index.lookup("00050428381397")
    assert [(row.source, row.dsld_id) for row in shipped] == [
        ("catalog", "278454"),
        ("corpus", "278454"),
    ]
    corpus_only = index.lookup("04006381333931")
    assert [(row.source, row.dsld_id) for row in corpus_only] == [
        ("corpus", "900001"),
        ("corpus", "900002"),
    ]
    draft = corpus_only[0].draft_payload
    assert draft is not None
    assert "row_ledger" not in draft
    assert "safety_hits" not in draft["ingredientRows"][0]
    assert index.built_at == built_at


def test_identity_index_freshness_has_warn_and_block_boundaries():
    now = datetime(2026, 8, 25, 18, 0, tzinfo=timezone.utc)
    assert serve.identity_index_freshness(now - timedelta(days=29), now) == (
        "fresh"
    )
    assert serve.identity_index_freshness(now - timedelta(days=31), now) == (
        "warning"
    )
    assert serve.identity_index_freshness(now - timedelta(days=61), now) == (
        "blocked"
    )
    assert serve.IDENTITY_INDEX_WARN_DAYS == 30
    assert serve.IDENTITY_INDEX_BLOCK_DAYS == 60


def test_console_exposes_fail_closed_identity_actions():
    index_html = (REVIEW_DIR / "static" / "index.html").read_text()
    app_js = (REVIEW_DIR / "static" / "app.js").read_text()
    serve_source = (REVIEW_DIR / "serve.py").read_text()

    assert "/api/identity_lookup?gtin14=" in app_js
    assert "action: 'record_match'" in app_js
    assert "Use as draft for label comparison" in app_js
    assert "/api/dsld_refresh" in app_js
    for outcome in (
        "catalog_match",
        "dsld_match",
        "identity_ambiguous",
        "no_match_verified",
        "not_this_product",
    ):
        assert outcome in app_js
    assert 'id="identity-check"' in index_html
    assert 'id="identity-index-status"' in index_html
    assert "IDENTITY_INDEX_WARN_DAYS = 30" in serve_source
    assert "IDENTITY_INDEX_BLOCK_DAYS = 60" in serve_source


def test_console_editor_picture_and_terminal_state_contracts():
    index_html = (REVIEW_DIR / "static" / "index.html").read_text()
    app_js = (REVIEW_DIR / "static" / "app.js").read_text()
    styles = (REVIEW_DIR / "static" / "styles.css").read_text()

    for element_id in (
        "other-disclosure",
        "other-ingredients",
        "statements-list",
        "product-picture-options",
        "reviewer-image-file",
        "reviewer-image-rights",
        "reviewer-image-attestation",
        "photo-lightbox",
        "image-canvas",
        "image-rotate",
        "image-crop",
    ):
        assert f'id="{element_id}"' in index_html
    for disclosure in (
        "present",
        "declared_none",
        "included_on_facts_panel",
    ):
        assert f'value="{disclosure}"' in index_html
    assert "addNestedRow" in app_js
    assert "addIngredientForm" in app_js
    assert "addStatement" in app_js
    assert "state.payload = parsed" in app_js
    assert "state.client.storage" in app_js
    assert "uploadToSignedUrl" in app_js
    assert "source_rights" in app_js
    assert "product_image_photo_id" in app_js
    assert "product_image_reviewer_object_id" in app_js
    assert "setDecisionAvailability" in app_js
    assert "showModal()" in app_js
    assert "photo-lightbox" in styles


def test_console_offers_a_typed_product_identity_mismatch_rejection():
    index_html = (REVIEW_DIR / "static" / "index.html").read_text()

    assert 'value="product_identity_mismatch"' in index_html
    assert "Photos don’t match scanned product" in index_html
