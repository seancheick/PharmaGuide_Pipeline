"""Reviewer console server contract (scripts/submission_review/serve.py).

Pins the security shape of the local tool: loopback-only bind, a single
allowed proxy target (the deployed review Edge Function — never a
caller-chosen URL), parameterized catalog search, and the vendored
supabase-js bundle (pinned version, recorded checksum — no runtime CDN).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
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


def test_launcher_health_identifies_the_loaded_server_without_credentials():
    server = ThreadingHTTPServer((serve.BIND_HOST, 0), serve.ReviewerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://{serve.BIND_HOST}:{server.server_port}/api/health") as response:
            assert response.headers["cache-control"] == "no-store"
            health = json.load(response)
        assert health == {
            "service": "pharmaguide-submission-review", "version": 1,
            "server_sha256": hashlib.sha256((REVIEW_DIR / "serve.py").read_bytes()).hexdigest(),
        }
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
                    "quality_score_v4_100": 20,
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
                    "quality_score_v4_100": 95,
                    "ingredientRows": [{
                        "name": "Vitamin D3",
                        "quantity": [{"quantity": 50, "unit": "mcg"}],
                    }],
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
    assert [
        row.draft_payload["ingredientRows"][0]["quantity"][0]["quantity"]
        for row in corpus_only
    ] == [25, 50]
    assert all("quality_score_v4_100" not in row.draft_payload for row in corpus_only)
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


@pytest.mark.parametrize("new_source", ["catalog", "corpus", "invalid_corpus"])
def test_identity_lookup_finds_candidate_added_after_prior_no_match(tmp_path, new_source):
    catalog = tmp_path / "catalog.db"
    with sqlite3.connect(catalog) as connection:
        connection.execute(
            "create table products_core "
            "(dsld_id text, product_name text, brand_name text, upc_sku text)"
        )
    stage = tmp_path / "products" / "output_Test_enriched" / "enriched"
    stage.mkdir(parents=True)
    batch = stage / "enriched_cleaned_batch_1.json"

    def write_corpus(rows):
        batch.write_text(json.dumps(rows))
        (stage / ".stage_manifest.json").write_text(json.dumps({
            "schema_version": "1.0.0", "stage": "enrich",
            "processing_complete": True, "owned_files": [batch.name],
            "content_sha256": {
                batch.name: hashlib.sha256(batch.read_bytes()).hexdigest()
            },
        }))

    write_corpus([])

    class Handler(serve.ReviewerHandler):
        identity_index = serve.build_identity_index(catalog, tmp_path / "products")

    server = ThreadingHTTPServer((serve.BIND_HOST, 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = (
            f"http://{serve.BIND_HOST}:{server.server_port}"
            "/api/identity_lookup?gtin14=00050428381397"
        )
        with urllib.request.urlopen(url, timeout=5) as response:
            assert json.load(response)["matches"] == []
        if new_source == "catalog":
            with sqlite3.connect(catalog) as connection:
                connection.execute(
                    "insert into products_core values (?, ?, ?, ?)",
                    ("278454", "Vitamin D3", "Example Labs", "0050428381397"),
                )
        else:
            new_rows = [{
                "dsldId": 278454, "fullName": "Vitamin D3",
                "brandName": "Example Labs", "upcSku": "0050428381397",
            }]
            if new_source == "invalid_corpus":
                batch.write_text(json.dumps(new_rows))
                # A changed batch cannot serve the old no-match while its
                # manifest is invalid, even across repeated lookup attempts.
                for _ in range(2):
                    with pytest.raises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(url, timeout=5)
                    assert error.value.code == 503
            write_corpus(new_rows)
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.headers["cache-control"] == "no-store"
            assert [
                (row["source"], row["dsld_id"])
                for row in json.load(response)["matches"]
            ] == [
                ("catalog" if new_source == "catalog" else "corpus", "278454"),
            ]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


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


@pytest.mark.parametrize("action", ["record", "approve"])
@pytest.mark.parametrize("source_state", ["changed", "unavailable", "blocked", "current"])
def test_console_rechecks_identity_before_recording_or_approving(action, source_state):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for reviewer interaction tests")
    harness = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const [asset, action, sourceState] = process.argv.slice(1);
const previous = {
  canonical_gtin14: '00050428381397', index_built_at: '2026-09-08T12:00:00Z',
  index_revision: 'prior-source', freshness: 'fresh', matches: [],
};
const current = structuredClone(previous);
if (sourceState === 'changed') {
  current.index_revision = 'new-source';
  current.matches = [{source: 'corpus', dsld_id: '278454', brand_name: 'Example',
    product_name: 'Vitamin D3', upc_sku: '050428381397', draft_payload: {}}];
}
if (sourceState === 'blocked') current.freshness = 'blocked';
const calls = [];
const elements = new Map();
function element() {
  return {value: '', textContent: '', style: {}, classList: {add() {}, remove() {}},
    append() {}, addEventListener() {}};
}
const context = vm.createContext({
  structuredClone, previous, calls, action,
  document: {createElement: element, getElementById(id) {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  }},
  fetch: async (url, options) => {
    calls.push({url, body: options?.body ? JSON.parse(options.body) : null});
    if (url.startsWith('/api/identity_lookup')) {
      return {ok: sourceState !== 'unavailable', json: async () => (
        sourceState === 'unavailable' ? {error: 'identity index unavailable'} : current
      )};
    }
    return {ok: true, json: async () => ({})};
  },
});
// Boot and queue refresh concern login/listing, outside these decision actions.
vm.runInContext(fs.readFileSync(asset.replace('app.js','canonical.js'),'utf8'), context);
vm.runInContext(fs.readFileSync(asset, 'utf8') +
  '\nfunction boot() {}\nasync function loadQueue() {}\nasync function refreshSelected() {}', context);
(async () => {
  await vm.runInContext(`(async () => {
    state.selected = {id: 'submission', kind: 'missing_product', review_status:'under_review', normalized_upc: '050428381397', evidence_revision: 2, evidence_manifest_sha256: 'a'.repeat(64)};
    state.session = {access_token: 'reviewer-test-session'};
    state.identityLookup = previous;
    state.identityRecorded = 'no_match_verified';
    state.productImage = {kind: 'photo', id: 'front-photo'};
    state.payload = {};
    state.payloadCanonical=canonicalJson(state.payload);state.payloadSha='b'.repeat(64);
    state.diagnostics=[];  // the importer's validator has answered: nothing wrong

    state.verifiedKey=verificationKey();state.verified=new Set(CRITICAL_FIELDS.map(([key])=>key));
    try {
      if (action === 'record') await recordMatch('no_match_verified');
      else await approve();
    } catch (_) {}
  })()`, context);
  process.stdout.write(JSON.stringify({calls,
    recorded: vm.runInContext('state.identityRecorded', context)}));
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    result = subprocess.run(
        [node, "-e", harness, str(REVIEW_DIR / "static" / "app.js"), action, source_state],
        capture_output=True, text=True, check=True, timeout=15,
    )
    observed = json.loads(result.stdout)
    decisions = [row for row in observed["calls"] if row["url"] == "/api/edge"]
    if source_state == "current":
        assert len(decisions) == 1
        assert decisions[0]["body"]["expected_evidence_revision"] == 2
        assert decisions[0]["body"]["evidence_manifest_sha256"] == "a" * 64
        assert observed["calls"][0]["url"].startswith("/api/identity_lookup")
    else:
        assert decisions == []
        assert observed["recorded"] is None


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
