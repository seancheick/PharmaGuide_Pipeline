#!/usr/bin/env python3
"""Local reviewer console for product submissions.

Stdlib-only server that:

  * serves the static reviewer page (``static/``, vendored supabase-js —
    no runtime CDN);
  * proxies ``POST /api/edge`` to exactly ONE remote endpoint — the deployed
    ``review-product-submissions`` Edge Function — forwarding the browser's
    ``Authorization`` (reviewer JWT) and attaching the project ``apikey``.
    The function sets no CORS headers by design, so the browser cannot call
    it directly; this proxy is the CORS boundary and never widens it;
  * answers ``GET /api/catalog_search?q=`` from the released catalog SQLite
    (read-only, parameterized) so reviewers can resolve duplicate /
    already-in-catalog decisions against real identities.

Binds 127.0.0.1 only. The reviewer signs in in the browser (magic-link OTP)
with their own account; their uuid must be in the Edge Function's
``PRODUCT_SUBMISSION_REVIEWER_IDS`` allowlist.

Usage:
    SUPABASE_URL=... SUPABASE_ANON_KEY=... \
        python3 scripts/submission_review/serve.py [--port 8765] \
        [--catalog-db scripts/dist/pharmaguide_core.db]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# scripts/ on the path so the repo .env loads without overriding shell vars.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import env_loader  # noqa: E402,F401

BIND_HOST = "127.0.0.1"
EDGE_FUNCTION_PATH = "/functions/v1/review-product-submissions"
MAX_PROXY_BODY_BYTES = 2 * 1024 * 1024
STATIC_DIR = Path(__file__).resolve().parent / "static"
CATALOG_SEARCH_LIMIT = 20


def edge_function_url(supabase_url: str) -> str:
    """The single allowed proxy target."""
    return supabase_url.rstrip("/") + EDGE_FUNCTION_PATH


def search_catalog(catalog_db: Path, query: str) -> list[dict[str, str]]:
    """Parameterized identity search over the released catalog."""
    text = query.strip()
    if not text:
        return []
    digits = "".join(ch for ch in text if ch.isdigit())
    like = f"%{text}%"
    with sqlite3.connect(f"file:{catalog_db}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            """
            SELECT dsld_id, product_name, brand_name, upc_sku
              FROM products_core
             WHERE dsld_id = ?
                OR (? != '' AND REPLACE(REPLACE(REPLACE(REPLACE(
                      upc_sku, ' ', ''), '-', ''), '.', ''), '/', '') = ?)
                OR product_name LIKE ?
                OR brand_name LIKE ?
             ORDER BY product_name
             LIMIT ?
            """,
            (text, digits, digits, like, like, CATALOG_SEARCH_LIMIT),
        ).fetchall()
    return [
        {
            "dsld_id": str(row[0]),
            "product_name": str(row[1] or ""),
            "brand_name": str(row[2] or ""),
            "upc_sku": str(row[3] or ""),
        }
        for row in rows
    ]


class ReviewerHandler(SimpleHTTPRequestHandler):
    """Static files + the two /api endpoints."""

    server_version = "PGSubmissionReview/1"
    supabase_url = ""
    anon_key = ""
    catalog_db = Path("scripts/dist/pharmaguide_core.db")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 (stdlib naming)
        if self.path == "/api/config":
            # The anon key is a public client credential by design.
            self._json({
                "supabase_url": self.supabase_url,
                "anon_key": self.anon_key,
            })
            return
        if self.path.startswith("/api/catalog_search"):
            from urllib.parse import parse_qs, urlparse

            query = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            if len(query) > 200:
                self._json({"error": "query too long"}, 400)
                return
            try:
                results = search_catalog(self.catalog_db, query)
            except sqlite3.Error:
                self._json({"error": "catalog unavailable"}, 503)
                return
            self._json({"results": results})
            return
        if self.path.startswith("/api/"):
            self._json({"error": "not found"}, 404)
            return
        super().do_GET()

    def do_POST(self):  # noqa: N802
        if self.path != "/api/edge":
            self._json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("content-length") or 0)
        if length <= 0 or length > MAX_PROXY_BODY_BYTES:
            self._json({"error": "invalid body"}, 400)
            return
        body = self.rfile.read(length)
        authorization = self.headers.get("authorization")
        if not authorization or not authorization.startswith("Bearer "):
            self._json({"error": "reviewer session required"}, 401)
            return

        request = urllib.request.Request(
            edge_function_url(self.supabase_url),
            data=body,
            method="POST",
            headers={
                "content-type": "application/json",
                "authorization": authorization,
                "apikey": self.anon_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
                status = response.status
        except urllib.error.HTTPError as error:
            payload = error.read()
            status = error.code
        except OSError:
            self._json({"error": "edge function unreachable"}, 502)
            return
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):  # noqa: A002
        sys.stderr.write(
            "%s - %s\n" % (self.log_date_time_string(), format % args)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--catalog-db",
        type=Path,
        default=Path("scripts/dist/pharmaguide_core.db"),
    )
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    anon_key = (
        os.environ.get("SUPABASE_ANON_KEY", "").strip()
        or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    )
    if not supabase_url or not anon_key:
        print(
            "SUPABASE_URL and SUPABASE_ANON_KEY are required "
            "(reviewer JWT comes from the browser session).",
            file=sys.stderr,
        )
        return 2

    ReviewerHandler.supabase_url = supabase_url
    ReviewerHandler.anon_key = anon_key
    ReviewerHandler.catalog_db = args.catalog_db

    server = ThreadingHTTPServer((BIND_HOST, args.port), ReviewerHandler)
    print(f"Reviewer console: http://{BIND_HOST}:{args.port}/")
    print(f"Proxy target    : {edge_function_url(supabase_url)}")
    print(f"Catalog search  : {args.catalog_db}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
