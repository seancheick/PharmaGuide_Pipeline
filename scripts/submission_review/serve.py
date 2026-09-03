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
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# scripts/ on the path so the repo .env loads without overriding shell vars.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import env_loader  # noqa: E402,F401
from stage_manifest import MANIFEST_NAME, select_stage_files  # noqa: E402

BIND_HOST = "127.0.0.1"
EDGE_FUNCTION_PATH = "/functions/v1/review-product-submissions"
MAX_PROXY_BODY_BYTES = 2 * 1024 * 1024
MAX_PHOTO_BODY_BYTES = 20 * 1024 * 1024
STATIC_DIR = Path(__file__).resolve().parent / "static"
CATALOG_SEARCH_LIMIT = 20
IDENTITY_INDEX_WARN_DAYS = 30
IDENTITY_INDEX_BLOCK_DAYS = 60
GTIN_INPUT_PATTERN = re.compile(r"^[0-9\s-]+$")
GTIN_GOLDEN_PATH = Path(__file__).resolve().parent / "fixtures" / "gtin_golden.json"
GTIN_GOLDEN_SHA256 = (
    "d96e600c74654f813da95246ef1d027c042ba62eac7eb05675bcdf58c728f4dc"
)
_MANUAL_LABEL_TOP_LEVEL_FIELDS = frozenset({
    "brandName", "fullName", "ingredientRows", "nutritionalInfo", "offMarket",
    "otherIngredients", "otherIngredientsDisclosure", "physicalState",
    "productType", "servingSizes", "servingsPerContainer", "statements",
})
_MANUAL_LABEL_INGREDIENT_FIELDS = frozenset({
    "alternateNames", "category", "description", "forms", "ingredientGroup",
    "ingredientId", "name", "nestedRows", "notes", "order", "quantity",
    "uniiCode",
})
_MANUAL_LABEL_QUANTITY_FIELDS = frozenset({
    "dailyValueTargetGroup", "operator", "quantity", "servingSizeOrder",
    "servingSizeQuantity", "servingSizeUnit", "unit",
})
_MANUAL_LABEL_FORM_FIELDS = frozenset({
    "category", "ingredientGroup", "ingredientId", "name", "order", "percent",
    "prefix", "uniiCode",
})
_MANUAL_LABEL_SERVING_FIELDS = frozenset({
    "inSFB", "maxDailyServings", "maxQuantity", "minDailyServings",
    "minQuantity", "notes", "order", "unit",
})
_MANUAL_LABEL_STATEMENT_FIELDS = frozenset({"notes", "type"})
_MANUAL_LABEL_CLASSIFICATION_FIELDS = frozenset({
    "langualCode", "langualCodeDescription", "name",
})


@dataclass(frozen=True)
class IdentityCandidate:
    """One exact product identity from a named local source."""

    source: str
    dsld_id: str
    product_name: str
    brand_name: str
    upc_sku: str
    draft_payload: dict[str, object] | None = None


@dataclass(frozen=True)
class IdentityIndex:
    """Immutable exact GTIN-14 index built from released + full corpus data."""

    built_at: datetime
    matches: dict[str, tuple[IdentityCandidate, ...]]

    def lookup(self, canonical_gtin14: str) -> list[IdentityCandidate]:
        if not _is_valid_gtin(canonical_gtin14) or len(canonical_gtin14) != 14:
            return []
        return list(self.matches.get(canonical_gtin14, ()))


def _is_valid_gtin(value: str) -> bool:
    if len(value) not in {8, 12, 13, 14} or not value.isdigit():
        return False
    weighted_sum = 0
    for position_from_right, digit in enumerate(reversed(value[:-1]), start=1):
        weighted_sum += int(digit) * (3 if position_from_right % 2 else 1)
    return (10 - weighted_sum % 10) % 10 == int(value[-1])


def _expand_upce(value: str) -> str | None:
    if len(value) != 8 or not value.isdigit() or value[0] not in {"0", "1"}:
        return None
    number_system, d1, d2, d3, d4, d5, d6, check_digit = value
    if d6 in {"0", "1", "2"}:
        body = f"{number_system}{d1}{d2}{d6}0000{d3}{d4}{d5}"
    elif d6 == "3":
        body = f"{number_system}{d1}{d2}{d3}00000{d4}{d5}"
    elif d6 == "4":
        body = f"{number_system}{d1}{d2}{d3}{d4}00000{d5}"
    else:
        body = f"{number_system}{d1}{d2}{d3}{d4}{d5}0000{d6}"
    expanded = body + check_digit
    return expanded if _is_valid_gtin(expanded) else None


def canonical_gtin14_candidates(value: object) -> set[str]:
    """Return exact canonical interpretations using the Flutter GTIN rules."""
    raw = str(value or "").strip()
    if not raw or not GTIN_INPUT_PATTERN.fullmatch(raw):
        return set()
    digits = re.sub(r"[^0-9]", "", raw)
    candidates: set[str] = set()
    if _is_valid_gtin(digits):
        candidates.add(digits.rjust(14, "0"))
    if len(digits) == 8:
        expanded = _expand_upce(digits)
        if expanded is not None:
            candidates.add(expanded.rjust(14, "0"))
    return candidates


def validate_submission_photo_url(value: object, supabase_url: str) -> str:
    """Accept only signed private submission-photo URLs from this project."""
    from urllib.parse import parse_qs, urlparse

    raw = str(value or "").strip()
    source = urlparse(raw)
    project = urlparse(supabase_url)
    photo_prefix = (
        "/storage/v1/object/sign/product-submission-photos/"
    )
    query = parse_qs(source.query, keep_blank_values=True)
    if (
        source.scheme != "https"
        or source.netloc != project.netloc
        or source.username is not None
        or source.password is not None
        or not source.path.startswith(photo_prefix)
        or source.path == photo_prefix
        or source.fragment
        or set(query) != {"token"}
        or len(query["token"]) != 1
        or not query["token"][0]
    ):
        raise ValueError("invalid submission photo URL")
    return raw


def _verify_gtin_fixture() -> None:
    if hashlib.sha256(GTIN_GOLDEN_PATH.read_bytes()).hexdigest() != (
        GTIN_GOLDEN_SHA256
    ):
        raise ValueError("reviewer GTIN fixture does not match the Flutter contract")


def _allowed_fields(value: object, allowed: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {key: field for key, field in value.items() if key in allowed}


def _project_ingredient_row(value: object) -> dict[str, object]:
    """Strip enrichment-only fields from a reviewer draft ingredient row."""
    row = _allowed_fields(value, _MANUAL_LABEL_INGREDIENT_FIELDS)
    row["quantity"] = [
        _allowed_fields(item, _MANUAL_LABEL_QUANTITY_FIELDS)
        for item in row.get("quantity", [])
        if isinstance(item, dict)
    ]
    row["forms"] = [
        _allowed_fields(item, _MANUAL_LABEL_FORM_FIELDS)
        for item in row.get("forms", [])
        if isinstance(item, dict)
    ]
    row["nestedRows"] = [
        _project_ingredient_row(item)
        for item in row.get("nestedRows", [])
        if isinstance(item, dict)
    ]
    return row


def _manual_label_draft(product: dict[str, object]) -> dict[str, object]:
    """Project corpus truth into the exact, bounded manual-label vocabulary."""
    draft = _allowed_fields(product, _MANUAL_LABEL_TOP_LEVEL_FIELDS)
    draft["ingredientRows"] = [
        _project_ingredient_row(item)
        for item in draft.get("ingredientRows", [])
        if isinstance(item, dict)
    ]
    draft["servingSizes"] = [
        _allowed_fields(item, _MANUAL_LABEL_SERVING_FIELDS)
        for item in draft.get("servingSizes", [])
        if isinstance(item, dict)
    ]
    draft["statements"] = [
        _allowed_fields(item, _MANUAL_LABEL_STATEMENT_FIELDS)
        for item in draft.get("statements", [])
        if isinstance(item, dict)
    ]
    for field in ("physicalState", "productType"):
        if field in draft:
            draft[field] = _allowed_fields(
                draft[field], _MANUAL_LABEL_CLASSIFICATION_FIELDS
            )
    return draft


def identity_index_freshness(
    built_at: datetime,
    now: datetime | None = None,
) -> str:
    """Classify the source snapshot age at the reviewed 30/60-day bounds."""
    current = now or datetime.now(timezone.utc)
    built = built_at.astimezone(timezone.utc)
    age = current.astimezone(timezone.utc) - built
    if age > timedelta(days=IDENTITY_INDEX_BLOCK_DAYS):
        return "blocked"
    if age > timedelta(days=IDENTITY_INDEX_WARN_DAYS):
        return "warning"
    return "fresh"


def _iter_enriched_products(products_dir: Path):
    manifests = sorted(
        products_dir.glob(f"output_*_enriched/enriched/{MANIFEST_NAME}")
    )
    if not manifests:
        raise ValueError(
            f"no manifest-owned enriched corpus found under {products_dir}"
        )
    for manifest in manifests:
        for source in select_stage_files(
            [manifest.parent],
            "enrich",
            require_manifest=True,
        ):
            payload = json.loads(source.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                rows = payload
            elif isinstance(payload, dict):
                rows = next(
                    (
                        payload[key]
                        for key in ("products", "items", "data")
                        if isinstance(payload.get(key), list)
                    ),
                    [payload] if payload.get("dsldId") or payload.get("dsld_id") else [],
                )
            else:
                raise ValueError(f"unsupported enriched payload: {source}")
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"non-object enriched row: {source}")
                yield row


def _catalog_generated_at(connection: sqlite3.Connection, catalog_db: Path) -> datetime:
    try:
        row = connection.execute(
            "select value from export_manifest where key = 'generated_at'"
        ).fetchone()
    except sqlite3.Error:
        row = None
    if row and row[0]:
        parsed = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc)
    return datetime.fromtimestamp(catalog_db.stat().st_mtime, timezone.utc)


def build_identity_index(
    catalog_db: Path,
    products_dir: Path,
    *,
    built_at: datetime | None = None,
) -> IdentityIndex:
    """Build the exact released-catalog + manifest-owned corpus index."""
    catalog_db = Path(catalog_db).resolve()
    products_dir = Path(products_dir).resolve()
    _verify_gtin_fixture()
    by_gtin: dict[str, dict[tuple[str, str], IdentityCandidate]] = {}

    def add(candidate: IdentityCandidate) -> None:
        for gtin14 in canonical_gtin14_candidates(candidate.upc_sku):
            by_gtin.setdefault(gtin14, {})[(candidate.source, candidate.dsld_id)] = (
                candidate
            )

    with sqlite3.connect(f"file:{catalog_db}?mode=ro", uri=True) as connection:
        if built_at is None:
            built_at = _catalog_generated_at(connection, catalog_db)
        for row in connection.execute(
            "select dsld_id, product_name, brand_name, upc_sku "
            "from products_core where upc_sku is not null and trim(upc_sku) <> ''"
        ):
            add(
                IdentityCandidate(
                    source="catalog",
                    dsld_id=str(row[0]),
                    product_name=str(row[1] or ""),
                    brand_name=str(row[2] or ""),
                    upc_sku=str(row[3] or ""),
                    draft_payload=None,
                )
            )

    for product in _iter_enriched_products(products_dir):
        dsld_id = str(product.get("dsldId") or product.get("dsld_id") or "").strip()
        if not dsld_id:
            raise ValueError("enriched product is missing dsld identity")
        add(
            IdentityCandidate(
                source="corpus",
                dsld_id=dsld_id,
                product_name=str(
                    product.get("fullName") or product.get("product_name") or ""
                ),
                brand_name=str(
                    product.get("brandName") or product.get("brand_name") or ""
                ),
                upc_sku=str(product.get("upcSku") or product.get("upc_sku") or ""),
                draft_payload=_manual_label_draft(product),
            )
        )

    source_order = {"catalog": 0, "corpus": 1}
    frozen = {
        gtin14: tuple(
            sorted(
                candidates.values(),
                key=lambda row: (source_order[row.source], row.dsld_id),
            )
        )
        for gtin14, candidates in by_gtin.items()
    }
    if built_at is None:
        raise ValueError("identity index has no source timestamp")
    return IdentityIndex(built_at=built_at, matches=frozen)


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
    identity_index: IdentityIndex | None = None
    dsld_import_dir = Path(
        "~/Downloads/PharmaGuide_Datasets/staging/brands/User_Submissions"
    ).expanduser()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self) -> None:
        if not self.path.startswith("/api/"):
            self.send_header("cache-control", "no-store")
        super().end_headers()

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
        if self.path.startswith("/api/identity_lookup"):
            from urllib.parse import parse_qs, urlparse

            gtin14 = parse_qs(urlparse(self.path).query).get("gtin14", [""])[0]
            if len(gtin14) != 14 or not _is_valid_gtin(gtin14):
                self._json({"error": "exact canonical GTIN-14 required"}, 400)
                return
            if self.identity_index is None:
                self._json({"error": "identity index unavailable"}, 503)
                return
            self._json({
                "canonical_gtin14": gtin14,
                "index_built_at": self.identity_index.built_at.isoformat(),
                "freshness": identity_index_freshness(
                    self.identity_index.built_at
                ),
                "matches": [
                    asdict(candidate)
                    for candidate in self.identity_index.lookup(gtin14)
                ],
            })
            return
        if self.path.startswith("/api/"):
            self._json({"error": "not found"}, 404)
            return
        super().do_GET()

    def do_POST(self):  # noqa: N802
        if self.path not in {"/api/edge", "/api/dsld_refresh", "/api/photo"}:
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

        if self.path == "/api/photo":
            try:
                payload = json.loads(body)
                photo_url = validate_submission_photo_url(
                    payload.get("signed_url"),
                    self.supabase_url,
                )
                with urllib.request.urlopen(photo_url, timeout=30) as response:
                    content_type = response.headers.get_content_type()
                    photo = response.read(MAX_PHOTO_BODY_BYTES + 1)
                if not content_type.startswith("image/"):
                    raise ValueError("submission photo is not an image")
                if len(photo) > MAX_PHOTO_BODY_BYTES:
                    raise ValueError("submission photo is too large")
            except (ValueError, json.JSONDecodeError):
                self._json({"error": "invalid submission photo"}, 400)
                return
            except (urllib.error.HTTPError, OSError):
                self._json({"error": "submission photo unavailable"}, 502)
                return
            self.send_response(200)
            self.send_header("content-type", content_type)
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", str(len(photo)))
            self.end_headers()
            self.wfile.write(photo)
            return

        if self.path == "/api/dsld_refresh":
            try:
                payload = json.loads(body)
                dsld_id = str(payload.get("dsld_id") or "")
                if not re.fullmatch(r"[0-9]{1,30}", dsld_id):
                    raise ValueError("invalid DSLD identity")
                command = [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "dsld_api_sync.py"),
                    "refresh-ids",
                    "--ids",
                    dsld_id,
                    "--output-dir",
                    str(self.dsld_import_dir),
                ]
                result = subprocess.run(
                    command,
                    cwd=str(Path(__file__).resolve().parents[2]),
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0 or f"Wrote 1/1" not in result.stdout:
                    self._json({"error": "DSLD refresh failed"}, 502)
                    return
                self._json({
                    "imported": True,
                    "dsld_id": dsld_id,
                    "dataset": self.dsld_import_dir.name,
                })
            except (ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
                self._json({"error": "DSLD refresh failed"}, 400)
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
    parser.add_argument(
        "--enriched-corpus-dir",
        type=Path,
        default=Path("scripts/products"),
    )
    parser.add_argument(
        "--dsld-import-dir",
        type=Path,
        default=Path(
            os.environ.get(
                "PHARMAGUIDE_SUBMISSION_IMPORT_DIR",
                "~/Downloads/PharmaGuide_Datasets/staging/brands/User_Submissions",
            )
        ).expanduser(),
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
    ReviewerHandler.dsld_import_dir = args.dsld_import_dir
    try:
        ReviewerHandler.identity_index = build_identity_index(
            args.catalog_db,
            args.enriched_corpus_dir,
        )
    except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as error:
        print(f"Identity index unavailable: {error}", file=sys.stderr)
        return 2

    server = ThreadingHTTPServer((BIND_HOST, args.port), ReviewerHandler)
    print(f"Reviewer console: http://{BIND_HOST}:{args.port}/")
    print(f"Proxy target    : {edge_function_url(supabase_url)}")
    print(f"Catalog search  : {args.catalog_db}")
    print(
        "Identity index : "
        f"{ReviewerHandler.identity_index.built_at.isoformat()} "
        f"({identity_index_freshness(ReviewerHandler.identity_index.built_at)})"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
