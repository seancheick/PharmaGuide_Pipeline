"""Reviewer console server contract (scripts/submission_review/serve.py).

Pins the security shape of the local tool: loopback-only bind, a single
allowed proxy target (the deployed review Edge Function — never a
caller-chosen URL), parameterized catalog search, and the vendored
supabase-js bundle (pinned version, recorded checksum — no runtime CDN).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REVIEW_DIR = SCRIPTS_DIR / "submission_review"
sys.path.insert(0, str(REVIEW_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import serve  # noqa: E402

VENDORED_SUPABASE_JS = REVIEW_DIR / "static" / "vendor" / "supabase.js"
VENDORED_SUPABASE_SHA256 = (
    "2697f51bb3efa5f10b5b0bca2a39b3772b1b8f810e6885e3bb8d69c3242d5e07"
)


def test_server_binds_loopback_only():
    assert serve.BIND_HOST == "127.0.0.1"
    source = (REVIEW_DIR / "serve.py").read_text()
    assert "0.0.0.0" not in source


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


def test_catalog_search_is_parameterized_and_bounded(tmp_path):
    import sqlite3

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
