#!/usr/bin/env python3
"""Cert registry fetcher — stages reviewed-refresh candidates without changing live data.

Sources:
  - **live-nsf-sport** (production): GET www.nsfsport.com/certified-products/search-results.php
    returns all ~1253 NSF Certified for Sport Dietary Supplements in one HTML
    response. Optional --with-lots fetches per-product detail for lot numbers
    (~1253 extra requests, polite delay).
  - **live-nsf-173** (production): GET info.nsf.org/Certified/Dietary/Listings.asp
    returns all NSF/ANSI 173 Contents Certified products + companies in one
    HTML response.
  - **pdf** (fixture only): parses the 2020 DS-ABS PDF. Marked
    `audit_only=true` in the registry; the resolver's recency gate will block
    scoring against it. Useful as a regression fixture and for testing the
    resolver against historical data.
  - **live-consumerlab** (production): browser-fetches ConsumerLab's public
    CL Certified Products table. Only current bold rows are written; historical
    non-bold rows are excluded so expired seals do not score.

Multi-source: the registry holds records from all sources. Each verified_record
carries its `program` field; recency status is per-source.

Usage:
  # Candidate refresh (monthly; independent review before integration):
  python scripts/api_audit/verify_certifications.py --source live-nsf-sport
  python scripts/api_audit/verify_certifications.py --source live-nsf-sport --with-lots
  python scripts/api_audit/verify_certifications.py --source live-nsf-173
  python scripts/api_audit/verify_certifications.py --source live-consumerlab

  # All sources staged with failed snapshots preserved:
  python scripts/api_audit/verify_certifications.py --source all

  # PDF (fixture only, scoring_blocked by recency gate):
  python scripts/api_audit/verify_certifications.py --source pdf --dry-run

Retrieval never applies the candidate. Review refresh_report.json, response receipts,
identity/scope changes and missing override references before integrating validated
data through the usual behavioral-data gates. --merge-existing is retained as a
compatibility flag; candidates now always preserve untouched or failed sources.
"""

from __future__ import annotations

import argparse
import copy
from collections import Counter, defaultdict
import hashlib
import html
from html.parser import HTMLParser
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

REGISTRY_PATH = SCRIPTS_ROOT / "data" / "cert_registry.json"
FETCHER_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

from cert_resolver import normalize_brand, normalize_product, _sku_form_tokens  # noqa: E402


# Enabled only by the candidate-refresh CLI; direct parser/fetcher callers remain pure.
_RECEIPT_DIR: Path | None = None
_RECEIPTS: list[dict] = []


def _capture_body(url: str, body: bytes, status: int = 200) -> None:
    if _RECEIPT_DIR is None:
        return
    digest = hashlib.sha256(body).hexdigest()
    path = _RECEIPT_DIR / f"{len(_RECEIPTS):05d}-{digest[:16]}.response"
    path.write_bytes(body)
    _RECEIPTS.append({"url": url, "status": status, "sha256": digest,
                      "path": str(path), "retrieved_at": datetime.now(timezone.utc).isoformat()})


def _capture_response(response: requests.Response) -> None:
    if _RECEIPT_DIR is not None:
        _capture_body(response.url, response.content, response.status_code)


HTTP_HEADERS = {
    "User-Agent": "PharmaGuide-CertRegistryFetcher/1.0 (audit-only; contact: ops@pharmaguide)",
    "Accept": "text/html,application/xhtml+xml",
}
REQUEST_TIMEOUT = 30
POLITE_DELAY_SECONDS = 0.7  # between detail fetches


# ============================================================================
# NSF Sport (live) — www.nsfsport.com/certified-products/search-results.php
# ============================================================================

NSF_SPORT_SEARCH_URL = (
    "https://www.nsfsport.com/certified-products/search-results.php"
    "?keyword=&product_category=Dietary+Supplements&goal=&type=&brand="
)
NSF_SPORT_DETAIL_URL = "https://www.nsfsport.com/certified-products/listing-detail.php"


def fetch_nsf_sport_live(with_lots: bool = False) -> tuple[list[dict], str]:
    """Fetch the full NSF Sport DS list. Returns (records, snapshot_iso_date)."""
    from bs4 import BeautifulSoup

    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"GET {NSF_SPORT_SEARCH_URL}", file=sys.stderr)
    r = requests.get(NSF_SPORT_SEARCH_URL, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
    _capture_response(r)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    rows: list[dict] = []
    seen_ids: set[str] = set()
    for link in soup.select("a[href*='listing-detail.php']"):
        href = link.get("href", "")
        m = re.search(r"id=(\d+)", href)
        if not m:
            raise ValueError(f"Missing NSF Sport listing identity: {href}")
        listing_id = m.group(1)
        if listing_id in seen_ids:
            continue
        seen_ids.add(listing_id)

        # Product name from CSS hook
        name_el = link.select_one(".results__product-name")
        product_name = (name_el.get_text(strip=True) if name_el else "").strip()
        company_el = link.select_one(".results__company-name")
        declared_brand = company_el.get_text(strip=True) if company_el else ""
        # Image URL → embeds brand directory in path
        img_el = link.select_one("img.results__image, img.results__image, img")
        img_src = img_el.get("src", "") if img_el else ""
        brand_from_img = _brand_from_nsf_sport_img(img_src)

        if not product_name:
            raise ValueError(f"Missing NSF Sport product identity: {listing_id}")

        rows.append(
            {
                "listing_id": listing_id,
                "product_name": product_name,
                "brand_from_img": brand_from_img,
                "declared_brand": declared_brand,
                "thumbnail_url": img_src,
                "detail_url": urljoin(NSF_SPORT_DETAIL_URL, href),
            }
        )

    print(f"Found {len(rows)} NSF Sport DS listings", file=sys.stderr)

    if with_lots:
        print(f"Fetching per-product detail for lot numbers ({len(rows)} requests; polite {POLITE_DELAY_SECONDS}s)", file=sys.stderr)
        for i, row in enumerate(rows, 1):
            try:
                detail = _fetch_nsf_sport_detail(row["listing_id"])
                row.update(detail)
            except requests.RequestException as exc:
                raise ValueError(f"NSF Sport required detail failed: {row['listing_id']}: {exc}") from exc
            if i % 50 == 0:
                print(f"  [{i}/{len(rows)}] fetched", file=sys.stderr)
            time.sleep(POLITE_DELAY_SECONDS)

    records: list[dict] = []
    for row in rows:
        brand = (row.get("declared_brand") or row.get("manufacturer") or row.get("brand_from_img") or "").strip()
        if not brand:
            # Fall back to using the URL slug as brand. Better to skip than mislabel.
            brand = row.get("brand_from_img") or "UNKNOWN"
        product = row["product_name"]
        lots = row.get("lot_numbers", []) or []
        record_id = _make_record_id("NSF Sport", brand, product, lots, row["listing_id"])
        records.append(
            {
                "record_id": record_id,
                "program": "NSF Sport",
                "brand": brand,
                "product": product,
                "brand_normalized": normalize_brand(brand),
                "product_normalized": normalize_product(product),
                "scope": "sku",
                "lot_numbers_tested": lots,
                "verified_at": snapshot_date,
                "source_url": row["detail_url"],
                "evidence_band": "strong",
                "listing_id": row["listing_id"],
                "thumbnail_url": row.get("thumbnail_url"),
                "cert_date": row.get("cert_date"),
                "facility": row.get("facility"),
            }
        )
    return records, snapshot_date


def _brand_from_nsf_sport_img(img_src: str) -> str:
    """Derive brand from NSF Sport thumbnail URL (path-embedded).

    Real paths look like:
      https://info.nsf.org/Certified/Common/cfs/<code1>/<code2>/<Brand>/<Line>/<listing_id>/Product_01_tn.png
    The brand is the directory two levels above the numeric listing_id.
    """
    if not img_src:
        return ""
    from urllib.parse import unquote
    parts = img_src.split("/")
    # Find the numeric listing-id segment
    for i, part in enumerate(parts):
        if part.isdigit() and i >= 2:
            return unquote(parts[i - 2]).replace("+", " ").replace("%20", " ").strip()
    return ""


def parse_nsf_sport_detail_html(html_text: str) -> dict:
    """Parse an NSF Sport listing-detail page for lot numbers + facility metadata.

    The page is a ``<tr><th>Field</th><td>value<br>value…</td></tr>`` table, e.g.
    ``<tr><th>Lot #</th><td>48715<br/>49759<br/>…</td></tr>`` — so the values are
    in the cell adjacent to a header label, NOT on the same text line with a
    ``:``/``-`` separator. (The previous same-line regex required a separator the
    live page never emits, so lot capture silently returned nothing.)
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_text, "lxml")
    out: dict = {}
    for th in soup.find_all("th"):
        label = th.get_text(" ", strip=True).lower()
        td = th.find_next("td")
        if td is None:
            continue
        values = [ln.strip() for ln in td.get_text("\n", strip=True).split("\n") if ln.strip()]
        if not values:
            continue
        if label.startswith("lot"):
            out["lot_numbers"] = values
        elif "manufacturer" in label or label in ("company", "brand"):
            out.setdefault("manufacturer", values[0])
        elif "date" in label and ("certif" in label or "registered" in label):
            out.setdefault("cert_date", values[0])
        elif label.startswith("facility"):
            out.setdefault("facility", values[0])
    return out


def _fetch_nsf_sport_detail(listing_id: str) -> dict:
    """Fetch lot numbers and facility metadata from one NSF Sport detail page."""
    url = f"{NSF_SPORT_DETAIL_URL}?id={listing_id}"
    r = requests.get(url, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
    _capture_response(r)
    r.raise_for_status()
    from bs4 import BeautifulSoup
    headers = {th.get_text(" ", strip=True).lower() for th in BeautifulSoup(r.text, "lxml").find_all("th")}
    if not headers.intersection({"product form", "flavor", "lot #", "facility", "manufacturer"}):
        raise ValueError(f"Unrecognized NSF Sport detail: {listing_id}")
    return parse_nsf_sport_detail_html(r.text)


# ============================================================================
# NSF/ANSI 173 (live) — info.nsf.org/Certified/Dietary/Listings.asp
# ============================================================================

NSF_173_URL = "https://info.nsf.org/Certified/Dietary/Listings.asp"


def fetch_nsf_173_live() -> tuple[list[dict], str]:
    """Fetch the full NSF/ANSI 173 Contents Certified DS list. One GET, no pagination."""
    from bs4 import BeautifulSoup

    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"GET {NSF_173_URL}", file=sys.stderr)
    r = requests.get(NSF_173_URL, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
    _capture_response(r)
    r.raise_for_status()
    # IIS doesn't send a charset HTTP header, so requests defaults to
    # ISO-8859-1 per RFC 2616. The page is actually UTF-8 (declared via
    # <meta charset="utf-8">). Force UTF-8 so registered-trademark "®"
    # decodes correctly instead of becoming "Â®" mojibake.
    r.encoding = "utf-8"

    # The page is a flat dump separated by <hr noshade> per company.
    # Strategy: split the HTML on <hr> boundaries, parse each chunk.
    html = r.text
    chunks = re.split(r"<hr\s+noshade\s*>", html, flags=re.IGNORECASE)
    print(f"Parsed {len(chunks)} company chunks", file=sys.stderr)

    records: list[dict] = []
    company_count = 0
    for chunk_html in chunks:
        chunk = BeautifulSoup(chunk_html, "lxml")
        # Company name: <font size='+2'> NAME&nbsp;</font>
        name_el = chunk.find("font", attrs={"size": "+2"})
        if not name_el:
            continue
        company_name = name_el.get_text(strip=True).rstrip("\xa0").strip()
        if not company_name:
            continue
        company_count += 1

        # Facilities — possibly multiple "<strong>Facility :</strong>City, ST"
        facilities = [
            el.find_next(string=True).strip() if el else ""
            for el in chunk.find_all(string=re.compile(r"Facility\s*:", re.IGNORECASE))
        ]

        # Finished Products table: rows after the "Finished Products" heading
        # Look for tables whose first <tr> contains "Trade Designation"
        finished_products: list[dict[str, str]] = []
        for table in chunk.find_all("table"):
            trs = table.find_all("tr", recursive=False) or table.find_all("tr")
            if not trs:
                continue
            header_cells = trs[0].find_all(["td", "th"], recursive=False)
            headers = [cell.get_text(" ", strip=True).casefold() for cell in header_cells]
            if not headers or headers[0] != "trade designation":
                continue
            columns = {name: i for i, name in enumerate(headers)}
            for tr in trs[1:]:
                tds = tr.find_all("td", recursive=False)
                if not tds:
                    continue
                cells = [td.get_text(" ", strip=True) for td in tds]
                # Type-code header rows have colspan and no proper layout
                if len(cells) < 2:
                    continue
                trade = cells[0]
                product_id = cells[columns["product id"]] if "product id" in columns and len(cells) > columns["product id"] else ""
                product_form = cells[columns["product form"]] if "product form" in columns and len(cells) > columns["product form"] else ""
                serving_col = next((i for name, i in columns.items() if "serving" in name or "daily dose" in name), None)
                serving = cells[serving_col] if serving_col is not None and len(cells) > serving_col else ""
                if not trade or trade.strip().startswith(("AA/", "BCAA")) and "/" in trade:
                    # Looks like a product-type-code header row (e.g. "AA/BCAAs/CBD/...")
                    continue
                finished_products.append(
                    {
                        "trade_designation": trade,
                        "product_id": product_id,
                        "product_form": product_form,
                        "serving_size": serving,
                    }
                )

        grouped: dict[tuple, dict] = {}
        for fp in finished_products:
            key = (fp["trade_designation"], fp["product_id"], _source_form_identity(fp["product_form"]))
            if key not in grouped:
                grouped[key] = {**fp, "source_listing_rows": []}
            grouped[key]["source_listing_rows"].append({**fp, "brand": company_name})
        for key, fp in grouped.items():
            product = fp["trade_designation"]
            record_id = _make_record_id("NSF Certified", company_name, product, [], json.dumps(key, sort_keys=True))
            records.append({
                "record_id": record_id, "program": "NSF Certified", "brand": company_name, "product": product,
                "brand_normalized": normalize_brand(company_name), "product_normalized": normalize_product(product),
                "scope": "sku", "lot_numbers_tested": [], "verified_at": snapshot_date,
                "source_url": NSF_173_URL, "evidence_band": "strong", "product_form": fp["product_form"],
                "product_id": fp["product_id"], "serving_size": fp["serving_size"],
                "source_listing_rows": fp["source_listing_rows"], "facilities": sorted(set(facilities)),
            })

    aggregated: dict[tuple, dict] = {}
    for row in records:
        identity = _listing_identity(row)
        if identity not in aggregated:
            row["record_id"] = _make_record_id("NSF Certified", row["brand"].casefold(), row["product"].casefold(), [], json.dumps(identity))
            aggregated[identity] = row
        else:
            aggregated[identity]["facilities"] = sorted(set(aggregated[identity]["facilities"]) | set(row["facilities"]))
            aggregated[identity]["source_listing_rows"].extend(row["source_listing_rows"])
    records = list(aggregated.values())

    print(f"NSF/ANSI 173: {company_count} companies → {len(records)} product records", file=sys.stderr)
    return records, snapshot_date


# ============================================================================
# NSF/ANSI 455-2 GMP (live) — info.nsf.org/Certified/455GMP/Listings.asp
# ============================================================================

NSF_455_GMP_URL = "https://info.nsf.org/Certified/455GMP/Listings.asp"
# 455-2 is the Dietary Supplements GMP standard (facility audit). Product
# Contents Certified / Certified for Sport are separate programs. Snapshot 455-2 only.
NSF_455_2_STANDARD = "455-2GMP"


def parse_nsf_455_listing(
    html_text: str, snapshot_date: str, standard_label: str = "NSF/ANSI 455-2"
) -> list[dict]:
    """Parse the NSF/ANSI 455-2 GMP facility-registration listing.

    These are FACILITY registrations (company + facility, no finished products),
    so each record carries ``scope='facility'`` and an empty ``product`` — the
    resolver brand-matches them to ``brand_only`` (manufacturer-trust signal),
    never B4a. Structure mirrors the NSF/ANSI 173 page: companies split by
    ``<hr noshade>``, name in ``<font size='+2'>``, NSF company id embedded in
    the logo image path (``/logo/C0006061.gif``) → a verifiable per-company URL.
    """
    from bs4 import BeautifulSoup

    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    chunks = re.split(r"<hr\s+noshade\s*>", html_text, flags=re.IGNORECASE)
    for chunk_html in chunks:
        chunk = BeautifulSoup(chunk_html, "lxml")
        name_el = chunk.find("font", attrs={"size": "+2"})
        if not name_el:
            continue
        company = name_el.get_text(strip=True).rstrip("\xa0").strip()
        if not company or company.upper().startswith("NSF"):
            continue
        cid_match = re.search(r"/logo/(C\d+)\.gif", chunk_html, re.IGNORECASE)
        cid = cid_match.group(1) if cid_match else ""
        source_url = (
            f"{NSF_455_GMP_URL}?Company={cid}&Standard={NSF_455_2_STANDARD}"
            if cid
            else f"{NSF_455_GMP_URL}?Standard={NSF_455_2_STANDARD}"
        )
        key = (normalize_brand(company), cid)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "record_id": _make_record_id("NSF/ANSI 455", company, "", [], cid),
                "program": "NSF/ANSI 455",
                "brand": company,
                "product": "",
                "brand_normalized": normalize_brand(company),
                "product_normalized": "",
                "scope": "facility",
                "lot_numbers_tested": [],
                "verified_at": snapshot_date,
                "source_url": source_url,
                "evidence_band": "strong",
                "standard": standard_label,
                "company_id": cid or None,
            }
        )
    return records


def fetch_nsf_455_live() -> tuple[list[dict], str]:
    """Fetch NSF/ANSI 455-2 (Dietary Supplements GMP) facility registrations."""
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"{NSF_455_GMP_URL}?Standard={NSF_455_2_STANDARD}"
    print(f"GET {url}", file=sys.stderr)
    r = requests.get(url, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
    _capture_response(r)
    r.raise_for_status()
    r.encoding = "utf-8"
    records = parse_nsf_455_listing(r.text, snapshot_date)
    print(f"NSF/ANSI 455-2: {len(records)} facility registrations", file=sys.stderr)
    return records, snapshot_date


# ============================================================================
# USP Verified (live) — quality-supplements.org/usp_verified_products
# ============================================================================

USP_VERIFIED_URL = "https://www.quality-supplements.org/usp_verified_products"


class _USPProductListParser(HTMLParser):
    """Extract product cards from the public USP Verified product listing."""

    def __init__(self, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.products: list[dict[str, str]] = []
        self.next_href: str | None = None

        self._in_card = False
        self._card_div_depth = 0
        self._current: dict[str, str] = {}
        self._capturing_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: v or "" for k, v in attrs}
        class_attr = attrs_dict.get("class", "")

        if tag == "div" and not self._in_card and "views-col" in class_attr:
            self._in_card = True
            self._card_div_depth = 1
            self._current = {"source_page_url": self.page_url}
            self._title_parts = []
            return

        if self._in_card and tag == "div":
            self._card_div_depth += 1

        if self._in_card and tag == "img":
            alt = attrs_dict.get("alt", "")
            src = attrs_dict.get("src", "")
            brand = _brand_from_usp_logo_alt(alt)
            if brand:
                self._current["brand"] = brand
            if src:
                self._current["thumbnail_url"] = urljoin(self.page_url, src)

        if self._in_card and tag == "a":
            href = attrs_dict.get("href", "")
            if href:
                self._current["product_url"] = urljoin(self.page_url, href)
            self._capturing_title = True
            self._title_parts = []

        if tag == "a" and attrs_dict.get("rel") == "next":
            href = attrs_dict.get("href")
            if href:
                self.next_href = urljoin(self.page_url, href)

    def handle_data(self, data: str) -> None:
        if self._capturing_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capturing_title and tag == "a":
            title = re.sub(r"\s+", " ", " ".join(self._title_parts)).strip()
            if title:
                self._current["product"] = title
            self._capturing_title = False

        if self._in_card and tag == "div":
            self._card_div_depth -= 1
            if self._card_div_depth <= 0:
                self._finish_card()

    def _finish_card(self) -> None:
        if self._current.get("brand") and self._current.get("product"):
            self.products.append(dict(self._current))
        self._in_card = False
        self._card_div_depth = 0
        self._current = {}
        self._title_parts = []
        self._capturing_title = False


def _brand_from_usp_logo_alt(alt: str) -> str:
    """Convert card image alt text like 'Nature Made logo' to brand name."""
    if not alt:
        return ""
    brand = re.sub(r"\s+logo\s*$", "", alt.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", brand).strip()


def parse_usp_verified_listing_page(html: str, page_url: str) -> tuple[list[dict[str, str]], str | None]:
    """Parse one Quality-Supplements USP listing page.

    Returns (products, next_page_url). Product entries include brand, product,
    product_url, thumbnail_url, and source_page_url when available.
    """
    parser = _USPProductListParser(page_url)
    parser.feed(html)
    return parser.products, parser.next_href


def fetch_usp_verified_live(max_pages: int | None = None) -> tuple[list[dict], str]:
    """Fetch the public USP Verified product listing.

    The site is Akamai-protected and returns 403 to plain requests, but the
    public browser-rendered listing is static HTML once loaded. Use Playwright
    as an optional fetch dependency and keep parsing in stdlib code for tests.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "playwright is required to fetch USP Verified live listings because "
            "quality-supplements.org blocks plain requests. Install Playwright "
            "or run another source."
        ) from exc

    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    products: list[dict[str, str]] = []
    seen_products: set[tuple[str, str, str]] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page_url: str | None = USP_VERIFIED_URL
            page_count = 0
            visited_pages: set[str] = set()
            while page_url:
                if page_url in visited_pages:
                    raise ValueError("USP pagination cycle")
                visited_pages.add(page_url)
                if max_pages is not None and page_count >= max_pages:
                    break
                print(f"GET {page_url}", file=sys.stderr)
                navigation = page.goto(page_url, wait_until="domcontentloaded", timeout=60_000)
                html = page.content()
                _capture_body(page.url, html.encode("utf-8"), navigation.status if navigation else 0)
                if navigation is None or not navigation.ok:
                    raise ValueError(f"USP failed navigation: {page.url}")
                page_products, next_url = parse_usp_verified_listing_page(html, page.url)
                if not page_products:
                    raise ValueError(f"USP empty/unrecognized listing page: {page.url}")
                print(f"  parsed {len(page_products)} USP products", file=sys.stderr)
                for product in page_products:
                    key = (
                        normalize_brand(product.get("brand", "")),
                        normalize_product(product.get("product", "")),
                        product.get("product_url", ""),
                    )
                    if key in seen_products:
                        continue
                    seen_products.add(key)
                    products.append(product)
                page_count += 1
                page_url = next_url
        finally:
            browser.close()

    records: list[dict] = []
    for row in products:
        brand = row["brand"]
        product = row["product"]
        product_url = row.get("product_url", "")
        record_id = _make_record_id("USP Verified", brand, product, [], product_url)
        records.append(
            {
                "record_id": record_id,
                "program": "USP Verified",
                "brand": brand,
                "product": product,
                "brand_normalized": normalize_brand(brand),
                "product_normalized": normalize_product(product),
                "scope": "sku",
                "lot_numbers_tested": [],
                "verified_at": snapshot_date,
                "source_url": row.get("source_page_url") or USP_VERIFIED_URL,
                "product_url": product_url,
                "thumbnail_url": row.get("thumbnail_url"),
                "evidence_band": "strong",
            }
        )

    print(f"USP Verified: {len(records)} product records", file=sys.stderr)
    return records, snapshot_date


# ============================================================================
# Informed Choice / Informed Sport (live) — wetestyoutrust.com certified lists
# ============================================================================

INFORMED_CHOICE_URL = "https://choice.wetestyoutrust.com/certified-products"
INFORMED_SPORT_URL = "https://sport.wetestyoutrust.com/certified-products/"


class _InformedProductListParser(HTMLParser):
    """Extract brand-grouped products from Informed certified-product pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.products: list[dict[str, str]] = []
        self.listing_month: str | None = None
        self._current_brand: str | None = None
        self._tag_stack: list[str] = []
        self._capture_brand = False
        self._capture_product = False
        self._capture_month = False
        self._brand_parts: list[str] = []
        self._product_parts: list[str] = []
        self._month_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: v or "" for k, v in attrs}
        self._tag_stack.append(tag)
        class_attr = attrs_dict.get("class", "")

        if tag == "h3" and self.listing_month is None:
            self._capture_month = True
            self._month_parts = []

        if tag == "h4" and "small-bottom-margin" in class_attr:
            self._capture_brand = True
            self._brand_parts = []

        if tag == "span" and "field-content" in class_attr:
            self._capture_product = True
            self._product_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_brand:
            self._brand_parts.append(data)
        if self._capture_product:
            self._product_parts.append(data)
        if self._capture_month:
            self._month_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture_product and tag == "span":
            product = _clean_informed_text(" ".join(self._product_parts))
            if self._current_brand and product:
                self.products.append({"brand": self._current_brand, "product": product})
            self._capture_product = False
            self._product_parts = []

        if self._capture_brand and tag == "h4":
            brand = _clean_informed_text(" ".join(self._brand_parts))
            if brand:
                self._current_brand = brand
            self._capture_brand = False
            self._brand_parts = []

        if self._capture_month and tag == "h3":
            value = _clean_informed_text(" ".join(self._month_parts))
            if re.fullmatch(r"[A-Za-z]+-\d{4}", value):
                self.listing_month = value
            self._capture_month = False
            self._month_parts = []

        if self._tag_stack:
            self._tag_stack.pop()


def _clean_informed_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def parse_informed_certified_products_page(html_text: str) -> tuple[list[dict[str, str]], str | None]:
    """Parse one Informed certified-products page.

    Returns (products, listing_month). Each product has brand/product.
    """
    parser = _InformedProductListParser()
    parser.feed(html_text)
    return parser.products, parser.listing_month


def fetch_informed_live(program: str) -> tuple[list[dict], str]:
    """Fetch Informed Choice or Informed Sport certified-products listing."""
    if program == "Informed Choice":
        url = INFORMED_CHOICE_URL
    elif program == "Informed Sport":
        url = INFORMED_SPORT_URL
    else:
        raise ValueError(f"unsupported Informed program: {program}")

    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"GET {url}", file=sys.stderr)
    r = requests.get(url, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
    _capture_response(r)
    r.raise_for_status()
    r.encoding = "utf-8"
    products, listing_month = parse_informed_certified_products_page(r.text)

    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for row in products:
        brand = row["brand"]
        product = row["product"]
        key = (normalize_brand(brand), product.strip().casefold())
        if key in seen:
            continue
        seen.add(key)
        record_id = _make_record_id(program, brand, product, [], "")
        records.append(
            {
                "record_id": record_id,
                "program": program,
                "brand": brand,
                "product": product,
                "brand_normalized": normalize_brand(brand),
                "product_normalized": normalize_product(product),
                "scope": "sku",
                "lot_numbers_tested": [],
                "verified_at": snapshot_date,
                "source_url": url,
                "evidence_band": "strong",
                "listing_month": listing_month,
            }
        )

    print(f"{program}: {len(records)} product records", file=sys.stderr)
    return records, snapshot_date


# ============================================================================
# IFOS (live) — certifications.nutrasource.ca certified-products endpoint
# ============================================================================

NUTRASOURCE_CERTIFIED_PRODUCTS_URL = "https://certifications.nutrasource.ca/certified-products"
NUTRASOURCE_FILTERED_PRODUCTS_URL = (
    "https://certifications.nutrasource.ca/umbraco/surface/NutrasourceContent/GetFilteredProducts"
)
NUTRASOURCE_PRODUCT_DETAIL_URL = "https://certifications.nutrasource.ca/certified-products/product"
NUTRASOURCE_PRODUCT_IMAGE_BASE = "https://andi.nutrasource.ca/ProductImages/"
NUTRASOURCE_DETAIL_DELAY_SECONDS = 0.15


def parse_nutrasource_products_payload(payload: dict, program: str = "IFOS") -> tuple[list[dict[str, str]], int]:
    """Parse the Nutrasource filtered-products JSON response.

    The endpoint includes product IDs and names, but not brand names. Brand is
    resolved from each product detail page before records are written.
    """
    if program not in {"IFOS", "IKOS", "IAOS", "IPRO"}:
        raise ValueError(f"Unsupported Nutrasource program: {program}")
    if payload.get("success") is not True or not isinstance(payload.get("list"), list):
        raise ValueError("Malformed/failed Nutrasource listing response")
    total_count = int(payload.get("totalCount") or 0)
    rows: list[dict[str, str]] = []
    for item in payload.get("list", []) or []:
        if not item.get("Is" + program.capitalize()):
            continue
        product_num = str(item.get("ProductNum") or "").strip()
        product = _clean_nutrasource_text(str(item.get("ProductName") or ""))
        if not product_num or not product:
            continue
        thumbnail = str(item.get("ProductImage1") or "").strip()
        rows.append(
            {
                "product_num": product_num,
                "product": product,
                "thumbnail_url": urljoin(NUTRASOURCE_PRODUCT_IMAGE_BASE, thumbnail) if thumbnail else "",
            }
        )
    return rows, total_count


def parse_nutrasource_product_detail_page(html_text: str, product_num: str) -> dict[str, object]:
    """Parse one Nutrasource product detail page for brand + cert metadata."""
    title_match = re.search(r"<title>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if not title_match:
        return {}

    title = _clean_nutrasource_text(_strip_tags(title_match.group(1)))
    title_parts = [part.strip() for part in title.split("|")]
    if len(title_parts) < 3 or "certifications by nutrasource" not in title_parts[-1].lower():
        return {}

    product = title_parts[0]
    brand = title_parts[1]
    if not product or not brand:
        return {}

    brand_id_match = re.search(r"/certified-products/brand\?id=([A-Za-z0-9_-]+)", html_text)
    product_type_match = re.search(
        r"<strong>\s*Product Type:\s*</strong>\s*([^<]+)",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    certifications: list[str] = []
    for raw_cert in re.findall(r'<h2 class="h2--lg">\s*(.*?)\s*</h2>', html_text, flags=re.IGNORECASE | re.DOTALL):
        cert_text = _clean_nutrasource_text(_strip_tags(raw_cert)).lower()
        for program in ("IFOS", "IKOS", "IAOS", "IPRO"):
            if re.search(r"\b" + program.lower() + r"\b", cert_text):
                certifications.append(program)

    return {
        "brand": brand,
        "product": product,
        "brand_id": brand_id_match.group(1) if brand_id_match else "",
        "certifications": certifications,
        "product_type": _clean_nutrasource_text(product_type_match.group(1)) if product_type_match else "",
        "source_url": f"{NUTRASOURCE_PRODUCT_DETAIL_URL}?id={product_num}",
    }


def fetch_ifos_live(max_products: int | None = None, program: str = "IFOS") -> tuple[list[dict], str]:
    """Fetch an official Nutrasource program; additional programs are evidence-only.

    Nutrasource exposes product IDs via a JSON filtered-products endpoint. The
    product detail page is required to resolve brand names, so this performs one
    detail GET per IFOS product.
    """
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    page_size = 250
    page_number = 1
    products: list[dict[str, str]] = []
    seen_product_nums: set[str] = set()
    total_count: int | None = None

    while True:
        params = {
            "pageNumber": page_number,
            "pageSize": page_size,
            "forCertification": program,
            "forInterest": "",
            "forCategory": "",
            "byName": "",
        }
        print(f"GET {NUTRASOURCE_FILTERED_PRODUCTS_URL} page={page_number}", file=sys.stderr)
        r = requests.get(NUTRASOURCE_FILTERED_PRODUCTS_URL, params=params, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
        _capture_response(r)
        r.raise_for_status()
        payload = r.json()
        page_rows, total_count = parse_nutrasource_products_payload(payload, program=program)
        if not page_rows:
            break
        previous_ids = set(seen_product_nums)
        for row in page_rows:
            product_num = row["product_num"]
            if product_num in seen_product_nums:
                continue
            seen_product_nums.add(product_num)
            products.append(row)
            if max_products is not None and len(products) >= max_products:
                break
        if max_products is not None and len(products) >= max_products:
            break
        if not page_rows or (page_number > 1 and not any(row["product_num"] not in previous_ids for row in page_rows)):
            raise ValueError(f"{program} pagination made no progress")
        if total_count is not None and len(products) >= total_count:
            break
        page_number += 1

    if max_products is None and len(products) != total_count:
        raise ValueError(f"Incomplete {program} pagination: {len(products)} of {total_count}")

    print(f"{program}: found {len(products)} product IDs (reported total {total_count})", file=sys.stderr)

    records: list[dict] = []
    seen_records: set[str] = set()
    for i, row in enumerate(products, 1):
        product_num = row["product_num"]
        detail_url = f"{NUTRASOURCE_PRODUCT_DETAIL_URL}?id={product_num}"
        try:
            detail_response = requests.get(detail_url, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
            _capture_response(detail_response)
            detail_response.raise_for_status()
            detail = parse_nutrasource_product_detail_page(detail_response.text, product_num)
        except requests.RequestException as exc:
            print(f"  detail fetch failed for {product_num}: {exc}", file=sys.stderr)
            raise ValueError(f"{program} required detail failed: {product_num}: {exc}") from exc

        brand = str(detail.get("brand") or "").strip()
        product = str(detail.get("product") or row["product"]).strip()
        certifications = detail.get("certifications") or []
        if not brand or program not in certifications:
            print(f"  skipping {product_num}: missing brand or {program} detail certification", file=sys.stderr)
            raise ValueError(f"{program} required detail identity missing: {product_num}")

        key = product_num
        if key in seen_records:
            continue
        seen_records.add(key)
        record_id = _make_record_id(program, brand, product, [], product_num)
        records.append(
            {
                "record_id": record_id,
                "program": program,
                "brand": brand,
                "product": product,
                "brand_normalized": normalize_brand(brand),
                "product_normalized": normalize_product(product),
                "scope": "sku",
                "lot_numbers_tested": [],
                "verified_at": snapshot_date,
                "source_url": str(detail.get("source_url") or detail_url),
                "evidence_band": "strong",
                "product_num": product_num,
                "brand_id": detail.get("brand_id") or "",
                "product_type": detail.get("product_type") or "",
                "thumbnail_url": row.get("thumbnail_url") or "",
            }
        )

        if i % 50 == 0:
            print(f"  [{i}/{len(products)}] fetched IFOS details", file=sys.stderr)
        time.sleep(NUTRASOURCE_DETAIL_DELAY_SECONDS)

    print(f"{program}: {len(records)} product records", file=sys.stderr)
    return records, snapshot_date


def _strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "")


def _clean_nutrasource_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


# ============================================================================
# BSCG Certified Drug Free (live) — bscg.org/certified-drug-free-database
# ============================================================================

BSCG_DATABASE_URL = "https://www.bscg.org/certified-drug-free-database"
BSCG_AJAX_URL = "https://www.bscg.org/selected_program"
# `program` is a comma-separated set of numeric program codes; '1' == Certified
# Drug Free, the per-SKU banned-substance (anti-doping) program. Other codes
# (4=CBD, 5=animal supplements) are intentionally excluded here.
BSCG_DRUG_FREE_CODE = "1"
# The /selected_program endpoint sits behind a GoDaddy/Sucuri WAF that 403s plain
# requests. A browser-like UA + a seeding GET (captures the WAF cookie) + the
# Referer/Origin/X-Requested-With headers the page's own AJAX sends get accepted.
BSCG_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _clean_bscg_text(value: object) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def _parse_bscg_report_date(value: str) -> "datetime | None":
    """BSCG report dates look like '30 July 2022'. Tolerant parse for max()."""
    value = (value or "").strip()
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_bscg_products_payload(payload: list[dict], snapshot_date: str) -> list[dict]:
    """Collapse the BSCG /selected_program JSON into one SKU record per product.

    The endpoint returns every BSCG program; we keep only Certified-Drug-Free
    rows (program code '1'). BSCG certifies by lot, so a single product appears
    in many rows (one per tested lot). We group by authoritative product URL and carry
    every tested lot in ``lot_numbers_tested`` plus the most-recent report date —
    matching the registry's per-SKU shape (cf. NSF Sport) instead of emitting one
    redundant record per lot.
    """
    groups: dict[tuple[str, str], dict] = {}
    for item in payload:
        codes = {c.strip() for c in str(item.get("program", "")).split(",") if c.strip()}
        if BSCG_DRUG_FREE_CODE not in codes:
            continue
        company = _clean_bscg_text(item.get("company"))
        product = _clean_bscg_text(item.get("product"))
        if not company or not product:
            continue
        company_slug = str(item.get("company_slug") or "").strip()
        product_slug = str(item.get("product_slug") or "").strip()
        key = (company_slug, product_slug) if company_slug and product_slug else (company.casefold(), product.casefold())
        grp = groups.get(key)
        if grp is None:
            source_url = (
                f"{BSCG_DATABASE_URL}/{company_slug}/{product_slug}"
                if company_slug and product_slug
                else BSCG_DATABASE_URL
            )
            grp = groups[key] = {
                "company": company,
                "product": product,
                "lots": [],
                "categories": set(),
                "countries": set(),
                "report_dates": [],
                "source_url": source_url,
                "product_id": str(item.get("product_id") or ""),
            }
        lot = _clean_bscg_text(item.get("product_lot"))
        if lot and lot not in grp["lots"]:
            grp["lots"].append(lot)
        category = _clean_bscg_text(item.get("category"))
        if category:
            grp["categories"].add(category)
        country = _clean_bscg_text(item.get("countries_sold"))
        if country:
            grp["countries"].add(country)
        report_date = _clean_bscg_text(item.get("report_date"))
        if report_date:
            grp["report_dates"].append(report_date)

    records: list[dict] = []
    for grp in groups.values():
        latest_report = max(
            grp["report_dates"],
            key=lambda d: _parse_bscg_report_date(d) or datetime.min,
            default="",
        )
        records.append(
            {
                "record_id": _make_record_id(
                    "BSCG", grp["company"], grp["product"], grp["lots"], grp["product_id"]
                ),
                "program": "BSCG",
                "brand": grp["company"],
                "product": grp["product"],
                "brand_normalized": normalize_brand(grp["company"]),
                "product_normalized": normalize_product(grp["product"]),
                "scope": "sku",
                "lot_numbers_tested": grp["lots"],
                "verified_at": snapshot_date,
                "source_url": grp["source_url"],
                "evidence_band": "strong",
                "report_date": latest_report or None,
                "category": "; ".join(sorted(grp["categories"])) or None,
                "countries_sold": "; ".join(sorted(grp["countries"])) or None,
            }
        )
    return records


def fetch_bscg_live() -> tuple[list[dict], str]:
    """Fetch BSCG Certified Drug Free products from the public database.

    Data feeds a DataTables grid via POST /selected_program (JSON, program/cat/
    type filters; all-zero == everything). We seed a session GET to clear the WAF
    and filter to the Certified-Drug-Free program in the parser.
    """
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    session = requests.Session()
    base_headers = {"User-Agent": BSCG_BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"}

    print(f"GET {BSCG_DATABASE_URL} (seed WAF session)", file=sys.stderr)
    seed = session.get(BSCG_DATABASE_URL, headers=base_headers, timeout=REQUEST_TIMEOUT)
    _capture_response(seed)
    seed.raise_for_status()

    post_headers = {
        **base_headers,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": BSCG_DATABASE_URL,
        "Origin": "https://www.bscg.org",
    }
    print(f"POST {BSCG_AJAX_URL} (all programs)", file=sys.stderr)
    r = session.post(
        BSCG_AJAX_URL,
        headers=post_headers,
        data={"program_id": 0, "cat_id": 0, "type_id": 0},
        timeout=REQUEST_TIMEOUT,
    )
    _capture_response(r)
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, list):
        raise ValueError(f"unexpected BSCG payload type: {type(payload).__name__}")

    records = parse_bscg_products_payload(payload, snapshot_date)
    print(
        f"BSCG Certified Drug Free: {len(records)} product records "
        f"(collapsed from {len(payload)} program rows)",
        file=sys.stderr,
    )
    return records, snapshot_date


# ============================================================================
# ConsumerLab CL Certified Products (live) — consumerlab.com certified products
# ============================================================================

CONSUMERLAB_CERTIFIED_PRODUCTS_URL = "https://www.consumerlab.com/quality-certification-program/certified-products/"


def _clean_consumerlab_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _has_consumerlab_current_marker(cell: object) -> bool:
    """ConsumerLab marks current certifications with Bootstrap's fw-bold class."""
    try:
        class_values = cell.get("class") or []
        if isinstance(class_values, str):
            class_values = class_values.split()
        if "fw-bold" in class_values:
            return True
        return bool(cell.select_one(".fw-bold"))
    except AttributeError:
        return False


def parse_consumerlab_certified_products(
    html_text: str,
    snapshot_date: str,
    current_only: bool = True,
) -> list[dict]:
    """Parse ConsumerLab's public CL Certified Products table.

    ConsumerLab keeps historical certified products on the same page, while
    current products are shown in bold. Certifications are time-limited, so the
    production registry includes current rows only by default.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_text, "lxml")
    records: list[dict] = []
    seen: set[tuple[str, str, int | None]] = set()
    for tr in soup.select("table tr"):
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue
        product = _clean_consumerlab_text(cells[0].get_text(" ", strip=True))
        review_category = _clean_consumerlab_text(cells[1].get_text(" ", strip=True))
        brand = _clean_consumerlab_text(cells[2].get_text(" ", strip=True))
        year_text = _clean_consumerlab_text(cells[3].get_text(" ", strip=True))
        if not product or not brand:
            continue
        year_match = re.search(r"\b(20\d{2}|19\d{2})\b", year_text)
        certified_year = int(year_match.group(1)) if year_match else None
        current = _has_consumerlab_current_marker(cells[0]) or _has_consumerlab_current_marker(cells[3])
        if current_only and not current:
            continue
        key = (normalize_brand(brand), normalize_product(product), certified_year)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "record_id": _make_record_id(
                    "ConsumerLab",
                    brand,
                    product,
                    [],
                    str(certified_year or ""),
                ),
                "program": "ConsumerLab",
                "brand": brand,
                "product": product,
                "brand_normalized": normalize_brand(brand),
                "product_normalized": normalize_product(product),
                "scope": "sku",
                "lot_numbers_tested": [],
                "verified_at": snapshot_date,
                "source_url": CONSUMERLAB_CERTIFIED_PRODUCTS_URL,
                "evidence_band": "strong",
                "review_category": review_category or None,
                "certified_year": certified_year,
                "current_certification": current,
            }
        )
    return records


def fetch_consumerlab_live() -> tuple[list[dict], str]:
    """Fetch current ConsumerLab CL Certified product records.

    The public page is Cloudflare-protected for plain requests, but renders in a
    normal browser. Keep network fetching in Playwright and parsing in pure
    BeautifulSoup so parser tests stay deterministic and offline.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "playwright is required to fetch ConsumerLab live listings because "
            "consumerlab.com blocks plain requests. Install Playwright or run another source."
        ) from exc

    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"GET {CONSUMERLAB_CERTIFIED_PRODUCTS_URL}", file=sys.stderr)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                )
            )
            navigation = page.goto(CONSUMERLAB_CERTIFIED_PRODUCTS_URL, wait_until="domcontentloaded", timeout=60_000)
            _capture_body(page.url, page.content().encode("utf-8"), navigation.status if navigation else 0)
            if navigation is None or not navigation.ok:
                raise ValueError(f"ConsumerLab failed navigation: {page.url}")
            page.wait_for_selector("table tr", state="attached", timeout=15_000)
            rendered_html = page.content()
            _capture_body(page.url, rendered_html.encode("utf-8"), navigation.status)
        finally:
            browser.close()

    records = parse_consumerlab_certified_products(rendered_html, snapshot_date, current_only=True)
    print(f"ConsumerLab: {len(records)} current product records", file=sys.stderr)
    return records, snapshot_date


# ============================================================================
# PDF (fixture only, marked stale via recency gate)
# ============================================================================


def fetch_nsf_sport_pdf(pdf_path: Path) -> tuple[list[dict], str]:
    """Parse the DS-ABS PDF. Snapshot date defaults to PDF report date (2020-12-18)
    so the recency gate correctly blocks scoring."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise SystemExit("pip install pdfplumber") from exc

    rows: list[dict[str, str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                if not table:
                    continue
                header = [(c or "").strip().replace("\n", " ").lower() for c in table[0]]
                idx = {h: i for i, h in enumerate(header) if h}
                if "company name" not in idx:
                    continue
                for raw_row in table[1:]:
                    cells = [(c or "").strip() for c in raw_row]
                    if not any(cells):
                        continue

                    def _col(key: str) -> str:
                        pos = idx.get(key)
                        if pos is None or pos >= len(cells):
                            return ""
                        return re.sub(r"\s+", " ", cells[pos]).strip()

                    company = _col("company name")
                    trade = _col("trade designation")
                    if not company or not trade:
                        continue
                    lots_raw = _col("lot number")
                    lots = [lot.strip() for lot in re.split(r"[\n,;]+", lots_raw) if lot.strip()]
                    rows.append(
                        {
                            "company_name": company,
                            "trade_designation": trade,
                            "lot_numbers": lots,
                            "contact_email": _col("contact email"),
                            "contact_phone": _col("contact phone"),
                        }
                    )

    snapshot_date = "2020-12-18"  # PDF report date
    records: list[dict] = []
    for row in rows:
        brand = row["company_name"]
        product = row["trade_designation"]
        record_id = _make_record_id("NSF Sport", brand, product, row["lot_numbers"], "")
        records.append(
            {
                "record_id": record_id,
                "program": "NSF Sport",
                "brand": brand,
                "product": product,
                "brand_normalized": normalize_brand(brand),
                "product_normalized": normalize_product(product),
                "scope": "sku",
                "lot_numbers_tested": row["lot_numbers"],
                "verified_at": snapshot_date,
                "source_url": "https://info.nsf.org/Certified/NFL/DS-ABS_contacts.pdf",
                "evidence_band": "strong",
                "contact_email": row.get("contact_email") or None,
                "contact_phone": row.get("contact_phone") or None,
                "_fixture_only_note": "PDF snapshot 2020-12-18; recency gate blocks scoring",
            }
        )
    return records, snapshot_date


# ============================================================================
# Registry I/O
# ============================================================================


def _make_record_id(program: str, brand: str, product: str, lots: list[str], listing_id: str) -> str:
    base = f"{program}|{brand}|{product}|{listing_id}|{','.join(sorted(lots))}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    prefix = re.sub(r"[^A-Z]+", "_", program.upper())[:12].strip("_") or "CERT"
    return f"{prefix}_{digest.upper()}"


# Registry sources whose listings are facility audits rather than product
# certifications. scoring_v4.cert_evidence trusts audited-GMP facility evidence
# only from sources flagged here, so the flag is written on every refresh.
PROGRAM_AUDIT_SCOPE = {
    "NSF/ANSI 455": "gmp_facility",  # NSF/ANSI 455-2 GMP facility registration
}


def _source_form_identity(value: str) -> tuple:
    """Reuse the matcher form owner for simple singular/plural source forms.

    Compound preparations retain their full source text; canonical form tokens
    alone must not collapse coated, chewable or other named preparations.
    """
    text = (value or "").strip().casefold()
    tokens = _sku_form_tokens(text)
    if tokens and len(re.findall(r"[a-z]+", text)) == 1:
        return tuple(sorted(tokens))
    return (text,)


def _source_display_identity(record: dict) -> tuple:
    return record.get("program"), record.get("brand", "").strip().casefold(), record.get("product", "").strip().casefold(), _source_form_identity(record.get("product_form", "")), record.get("scope")


def _listing_identity(record: dict) -> tuple:
    """Authoritative listing identity; never collapse different forms via fuzzy names."""
    program = record.get("program")
    if program == "NSF Certified":
        return _source_display_identity(record), record.get("product_id", "").casefold()
    for key in ("listing_id", "product_num"):
        if record.get(key):
            return program, key, str(record[key])
    if record.get("company_id"):
        return program, "company_id", str(record["company_id"]), normalize_brand(record.get("brand", "")), record.get("scope"), record.get("product", ""), record.get("standard")
    url = record.get("product_url")
    if not url and program == "BSCG":
        url = record.get("source_url")
    if url:
        parts = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_") and k.lower() not in {"queryid", "s", "p"}]
        return program, "url", urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, urlencode(sorted(query)), ""))
    # Flat listings have no per-product source identifier. Preserve only exact
    # display identity, including strength/form, rather than normalized product.
    return program, "display", normalize_brand(record.get("brand", "")), re.sub(r"\s+", " ", record.get("product", "")).strip().casefold(), record.get("scope"), record.get("product_form"), record.get("product_type"), record.get("certified_year")


def build_refresh_candidate(previous: dict, sources: list[dict], failures: list[dict], overrides: list[dict]) -> tuple[dict, dict]:
    """Validate snapshots and report review deltas, without modifying the live registry."""
    candidate = copy.deepcopy(previous)
    records = candidate.setdefault("verified_records", [])
    metadata = candidate.setdefault("_metadata", {})
    source_meta = metadata.setdefault("registry_sources", [])
    report = {"programs": [], "missing_override_references": [], "review_required": True}
    for failure in failures:
        report["programs"].append({**failure, "status": "failed_preserved"})
    for source in sources:
        program = source["program"]
        incoming = copy.deepcopy(source["records"])
        old = [r for r in records if r.get("program") == program]
        try:
            if not incoming:
                raise ValueError("Empty/unrecognized snapshot requires review; old snapshot preserved")
            ids, identities = set(), set()
            old_by_identity = {}
            ambiguous_old_identities = set()
            old_display_ids = defaultdict(set)
            old_id_displays = defaultdict(set)
            incoming_display_counts = Counter(_source_display_identity(r) for r in incoming if isinstance(r, dict))
            for row in old:
                display = _source_display_identity(row)
                old_display_ids[display].add(row["record_id"])
                old_id_displays[row["record_id"]].add(display)
                identity = _listing_identity(row)
                if identity in old_by_identity and old_by_identity[identity]["record_id"] != row["record_id"]:
                    ambiguous_old_identities.add(identity)
                old_by_identity[identity] = row
            for row in incoming:
                if not isinstance(row, dict):
                    raise ValueError("Malformed certification record type")
                if row.get("program") != program or not all(row.get(k) for k in ("record_id", "brand", "source_url", "verified_at", "scope")):
                    raise ValueError("Malformed certification record")
                if row.get("brand") == "UNKNOWN" or (row.get("scope") != "facility" and not row.get("product")):
                    raise ValueError("Missing product/facility identity")
                if not isinstance(row["verified_at"], str):
                    raise ValueError("Malformed record verification date")
                datetime.strptime(row["verified_at"], "%Y-%m-%d")
                if row["verified_at"] != source["snapshot_date"]:
                    raise ValueError("Snapshot/record date mismatch")
                if row["scope"] not in {"sku", "product_line", "brand", "facility"}:
                    raise ValueError("Unrecognized certification scope")
                identity = _listing_identity(row)
                previous_row = old_by_identity.get(identity)
                if previous_row and previous_row.get("lot_numbers_tested") and not row.get("lot_numbers_tested"):
                    raise ValueError("Previous lot evidence cannot be erased by an empty/list-only refresh; verify current detail and review the withdrawal")
                if identity in identities or row["record_id"] in ids:
                    raise ValueError("Duplicate source identity or record ID")
                identities.add(identity)
                ids.add(row["record_id"])
                if identity in old_by_identity and identity not in ambiguous_old_identities and len(old_id_displays[old_by_identity[identity]["record_id"]]) == 1:
                    row["record_id"] = old_by_identity[identity]["record_id"]
                elif program == "NSF Certified":
                    display = _source_display_identity(row)
                    previous_ids = old_display_ids.get(display, set())
                    if len(previous_ids) == 1 and incoming_display_counts[display] == 1:
                        previous_id = next(iter(previous_ids))
                        if len(old_id_displays[previous_id]) == 1:
                            row["record_id"] = previous_id
            stable_ids = [r["record_id"] for r in incoming]
            if len(set(stable_ids)) != len(stable_ids):
                raise ValueError("Duplicate record IDs after preserving source identity")
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            report["programs"].append({"program": program, "status": "failed_preserved", "error": str(exc)})
            continue
        before = {r["record_id"]: r for r in old}
        after = {r["record_id"]: r for r in incoming}
        changed = [rid for rid in sorted(before.keys() & after.keys())
                   if {k: v for k, v in before[rid].items() if k != "verified_at"} != {k: v for k, v in after[rid].items() if k != "verified_at"}]
        report["programs"].append({"program": program, "status": "candidate_complete", "snapshot_date": source["snapshot_date"],
                                    "added": sorted(after.keys() - before.keys()), "removed": sorted(before.keys() - after.keys()),
                                    "changed": changed, "scope_changes": [rid for rid in changed if before[rid].get("scope") != after[rid].get("scope")],
                                    "split_previous_record_ids": sorted(rid for rid, displays in old_id_displays.items() if program == "NSF Certified" and (len(displays) > 1 or any(incoming_display_counts[d] > 1 or len(old_display_ids[d]) > 1 for d in displays))),
                                    "identity_changes": [rid for rid in changed if any(before[rid].get(k) != after[rid].get(k) for k in ("brand", "product", "product_form", "product_type", "scope"))],
                                    "lot_changes": [rid for rid in changed if before[rid].get("lot_numbers_tested") != after[rid].get("lot_numbers_tested")],
                                    "record_count": len(incoming)})
        records[:] = [r for r in records if r.get("program") != program] + incoming
        source_meta[:] = [s for s in source_meta if s.get("program") != program]
        entry = {"program": program, "url": source["url"], "snapshot_date": source["snapshot_date"], "entry_count": len(incoming)}
        if program in PROGRAM_AUDIT_SCOPE:
            entry["audit_scope"] = PROGRAM_AUDIT_SCOPE[program]
        source_meta.append(entry)
    live_ids = {r["record_id"] for r in records}
    report["missing_override_references"] = sorted({o["record_id"] for o in overrides if o.get("status") == "verified" and o.get("record_id") and o["record_id"] not in live_ids})
    previous_ids = {r["record_id"] for r in previous.get("verified_records", [])}
    report["preexisting_missing_override_references"] = [rid for rid in report["missing_override_references"] if rid not in previous_ids]
    report["new_missing_override_references"] = [rid for rid in report["missing_override_references"] if rid in previous_ids]
    if any(p["status"] == "candidate_complete" for p in report["programs"]):
        metadata["total_verified_records"] = len(records)
        for entry in source_meta:
            if entry.get("program") in PROGRAM_AUDIT_SCOPE:
                entry["audit_scope"] = PROGRAM_AUDIT_SCOPE[entry["program"]]
        metadata["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return candidate, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Cert registry fetcher")
    parser.add_argument(
        "--source",
        choices=[
            "live-nsf-sport",
            "live-nsf-173",
            "live-nsf-455",
            "live-usp",
            "live-informed-choice",
            "live-informed-sport",
            "live-ifos",
            "live-ikos",
            "live-iaos",
            "live-ipro",
            "live-bscg",
            "live-consumerlab",
            "pdf",
            "all",
        ],
        required=True,
    )
    parser.add_argument(
        "--with-lots",
        action="store_true",
        help="Fetch per-product detail for lot numbers (NSF Sport only, ~1253 extra requests).",
    )
    parser.add_argument(
        "--pdf-path",
        type=Path,
        default=Path("/Users/seancheick/Downloads/NSF_DS-ABS_contacts.pdf"),
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="Preserve existing registry sources not refreshed by this run.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit paginated/detail-heavy sources for smoke tests (USP pages or IFOS products).",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", type=Path, help="Durable candidate/response receipt directory; never the live registry directory.")
    args = parser.parse_args()
    if args.source == "pdf" and not args.dry_run:
        parser.error("PDF is historical fixture evidence; use --dry-run, not a production snapshot")
    if args.max_pages is not None and not args.dry_run:
        parser.error("--max-pages is a smoke-test limit and cannot produce a refresh candidate")
    output = args.output_dir or Path.home() / "pg_quality" / ("cert_refresh_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    if output.resolve() == REGISTRY_PATH.parent.resolve() or REGISTRY_PATH.resolve().is_relative_to(output.resolve()):
        parser.error("Candidate output must be outside the live registry directory")
    output.mkdir(parents=True, exist_ok=False)
    global _RECEIPT_DIR, _RECEIPTS
    _RECEIPT_DIR = output / "responses"
    _RECEIPT_DIR.mkdir()
    _RECEIPTS = []
    baseline_bytes = REGISTRY_PATH.read_bytes()
    baseline_hash = hashlib.sha256(baseline_bytes).hexdigest()
    previous = json.loads(baseline_bytes)
    (output / "baseline_registry.json").write_bytes(baseline_bytes)
    (output / "fetch_provenance.json").write_text(json.dumps({"baseline_sha256": baseline_hash, "fetcher_source_sha256": FETCHER_SOURCE_SHA256}, indent=2) + "\n")
    specs = [
        ("live-nsf-sport", "NSF Sport", NSF_SPORT_SEARCH_URL, lambda: fetch_nsf_sport_live(with_lots=args.with_lots)),
        ("live-nsf-173", "NSF Certified", NSF_173_URL, fetch_nsf_173_live),
        ("live-nsf-455", "NSF/ANSI 455", f"{NSF_455_GMP_URL}?Standard={NSF_455_2_STANDARD}", fetch_nsf_455_live),
        ("live-usp", "USP Verified", USP_VERIFIED_URL, lambda: fetch_usp_verified_live(max_pages=args.max_pages)),
        ("live-informed-choice", "Informed Choice", INFORMED_CHOICE_URL, lambda: fetch_informed_live("Informed Choice")),
        ("live-informed-sport", "Informed Sport", INFORMED_SPORT_URL, lambda: fetch_informed_live("Informed Sport")),
        ("live-ifos", "IFOS", NUTRASOURCE_CERTIFIED_PRODUCTS_URL, lambda: fetch_ifos_live(max_products=args.max_pages)),
        ("live-ikos", "IKOS", NUTRASOURCE_CERTIFIED_PRODUCTS_URL, lambda: fetch_ifos_live(max_products=args.max_pages, program="IKOS")),
        ("live-iaos", "IAOS", NUTRASOURCE_CERTIFIED_PRODUCTS_URL, lambda: fetch_ifos_live(max_products=args.max_pages, program="IAOS")),
        ("live-ipro", "IPRO", NUTRASOURCE_CERTIFIED_PRODUCTS_URL, lambda: fetch_ifos_live(max_products=args.max_pages, program="IPRO")),
        ("live-bscg", "BSCG", BSCG_DATABASE_URL, fetch_bscg_live),
        ("live-consumerlab", "ConsumerLab", CONSUMERLAB_CERTIFIED_PRODUCTS_URL, fetch_consumerlab_live),
        ("pdf", "NSF Sport", "https://info.nsf.org/Certified/NFL/DS-ABS_contacts.pdf", lambda: fetch_nsf_sport_pdf(args.pdf_path)),
    ]
    sources, failures, additional = [], [], []
    try:
        for name, program, url, fetch in specs:
            if args.source != name and not (args.source == "all" and name not in {"pdf", "live-ikos", "live-iaos", "live-ipro"}):
                continue
            start = len(_RECEIPTS)
            try:
                rows, snapshot = fetch()
                fetched = {"program": program, "url": url, "snapshot_date": snapshot, "records": rows}
                if program in {"IKOS", "IAOS", "IPRO"}:
                    additional.append(fetched)
                else:
                    sources.append(fetched)
            except (Exception, SystemExit) as exc:
                failures.append({"program": program, "error": str(exc)})
                print(f"{program}: failed; previous snapshot retained: {exc}", file=sys.stderr)
            finally:
                for receipt in _RECEIPTS[start:]:
                    receipt["program"] = program
                (output / "response_receipts.json").write_text(json.dumps(_RECEIPTS, indent=2) + "\n")
                (output / "source_snapshots.json").write_text(json.dumps(sources + additional, indent=2, ensure_ascii=False) + "\n")
        overrides_path = SCRIPTS_ROOT / "data" / "curated_overrides" / "cert_verification_overrides.json"
        overrides = json.loads(overrides_path.read_text()).get("overrides", [])
        candidate, report = build_refresh_candidate(previous, sources, failures, overrides)
        if hashlib.sha256(REGISTRY_PATH.read_bytes()).hexdigest() != baseline_hash:
            raise SystemExit("Registry changed during retrieval; snapshots retained, candidate withheld. Reconcile against the new baseline.")
        if additional:
            _, additional_report = build_refresh_candidate({"_metadata": {"registry_sources": []}, "verified_records": []}, additional, [], [])
            report["pending_policy_sources"] = [{**row, "status": "complete_policy_pending" if row["status"] == "candidate_complete" else row["status"]} for row in additional_report["programs"]]
            (output / "additional_programs.pending_policy.json").write_text(json.dumps(additional, indent=2) + "\n")
        report["pending_policy_programs"] = [s["program"] for s in additional]
        report.update(baseline_sha256=baseline_hash, fetcher_source_sha256=FETCHER_SOURCE_SHA256, smoke_test=args.dry_run,
                      receipt_count=len(_RECEIPTS), generated_at=datetime.now(timezone.utc).isoformat())
        (output / "refresh_report.json").write_text(json.dumps(report, indent=2) + "\n")
        if not args.dry_run:
            (output / "cert_registry.candidate.json").write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + "\n")
        print(f"Review candidate and source receipts: {output}")
        if any(row["status"] == "failed_preserved" for row in report["programs"] + report.get("pending_policy_sources", [])):
            raise SystemExit(1)
    finally:
        _RECEIPT_DIR = None


if __name__ == "__main__":
    main()
