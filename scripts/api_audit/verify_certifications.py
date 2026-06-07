#!/usr/bin/env python3
"""Cert registry fetcher — populates scripts/data/cert_registry.json.

Sources:
  - **live-nsf-sport** (production): GET nsfsport-prod.nsf.org/certified-products/search-results.php
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

Multi-source: the registry holds records from all sources. Each verified_record
carries its `program` field; recency status is per-source.

Usage:
  # Production refresh (recommended quarterly):
  python scripts/api_audit/verify_certifications.py --source live-nsf-sport
  python scripts/api_audit/verify_certifications.py --source live-nsf-sport --with-lots
  python scripts/api_audit/verify_certifications.py --source live-nsf-173

  # All sources merged:
  python scripts/api_audit/verify_certifications.py --source all

  # PDF (fixture only, scoring_blocked by recency gate):
  python scripts/api_audit/verify_certifications.py --source pdf

P0.1a is audit-only. Resolver consumes this registry; cert_audit_report.py
runs the audit. No scoring changes until P0.1b.
"""

from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

REGISTRY_PATH = SCRIPTS_ROOT / "data" / "cert_registry.json"

from cert_resolver import normalize_brand, normalize_product  # noqa: E402


HTTP_HEADERS = {
    "User-Agent": "PharmaGuide-CertRegistryFetcher/1.0 (audit-only; contact: ops@pharmaguide)",
    "Accept": "text/html,application/xhtml+xml",
}
REQUEST_TIMEOUT = 30
POLITE_DELAY_SECONDS = 0.7  # between detail fetches


# ============================================================================
# NSF Sport (live) — nsfsport-prod.nsf.org/certified-products/search-results.php
# ============================================================================

NSF_SPORT_SEARCH_URL = (
    "https://nsfsport-prod.nsf.org/certified-products/search-results.php"
    "?keyword=&product_category=Dietary+Supplements&goal=&type=&brand="
)
NSF_SPORT_DETAIL_URL = "https://nsfsport-prod.nsf.org/certified-products/listing-detail.php"


def fetch_nsf_sport_live(with_lots: bool = False) -> tuple[list[dict], str]:
    """Fetch the full NSF Sport DS list. Returns (records, snapshot_iso_date)."""
    from bs4 import BeautifulSoup

    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"GET {NSF_SPORT_SEARCH_URL}", file=sys.stderr)
    r = requests.get(NSF_SPORT_SEARCH_URL, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    rows: list[dict] = []
    seen_ids: set[str] = set()
    for link in soup.select("a[href*='listing-detail.php']"):
        href = link.get("href", "")
        m = re.search(r"id=(\d+)", href)
        if not m:
            continue
        listing_id = m.group(1)
        if listing_id in seen_ids:
            continue
        seen_ids.add(listing_id)

        # Product name from CSS hook
        name_el = link.select_one(".results__product-name")
        product_name = (name_el.get_text(strip=True) if name_el else "").strip()
        # Image URL → embeds brand directory in path
        img_el = link.select_one("img.results__image, img.results__image, img")
        img_src = img_el.get("src", "") if img_el else ""
        brand_from_img = _brand_from_nsf_sport_img(img_src)

        if not product_name:
            continue

        rows.append(
            {
                "listing_id": listing_id,
                "product_name": product_name,
                "brand_from_img": brand_from_img,
                "thumbnail_url": img_src,
                "detail_url": urljoin(NSF_SPORT_DETAIL_URL, href) if href.startswith("/") else href,
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
                row["_detail_error"] = str(exc)
            if i % 50 == 0:
                print(f"  [{i}/{len(rows)}] fetched", file=sys.stderr)
            time.sleep(POLITE_DELAY_SECONDS)

    records: list[dict] = []
    for row in rows:
        brand = (row.get("manufacturer") or row.get("brand_from_img") or "").strip()
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
    r.raise_for_status()
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
            el.find_next(text=True).strip() if el else ""
            for el in chunk.find_all(string=re.compile(r"Facility\s*:", re.IGNORECASE))
        ]

        # Finished Products table: rows after the "Finished Products" heading
        # Look for tables whose first <tr> contains "Trade Designation"
        finished_products: list[dict[str, str]] = []
        for table in chunk.find_all("table"):
            trs = table.find_all("tr", recursive=False) or table.find_all("tr")
            if not trs:
                continue
            header_text = trs[0].get_text(" ", strip=True).lower()
            if "trade designation" not in header_text:
                continue
            for tr in trs[1:]:
                tds = tr.find_all("td")
                if not tds:
                    continue
                cells = [td.get_text(" ", strip=True) for td in tds]
                # Type-code header rows have colspan and no proper layout
                if len(cells) < 2:
                    continue
                trade = cells[0]
                product_id = cells[1] if len(cells) > 1 else ""
                product_form = cells[2] if len(cells) > 2 else ""
                serving = cells[3] if len(cells) > 3 else ""
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

        for fp in finished_products:
            product = fp["trade_designation"]
            record_id = _make_record_id("NSF Certified", company_name, product, [], "")
            records.append(
                {
                    "record_id": record_id,
                    "program": "NSF Certified",  # NSF/ANSI 173 Contents Certified
                    "brand": company_name,
                    "product": product,
                    "brand_normalized": normalize_brand(company_name),
                    "product_normalized": normalize_product(product),
                    "scope": "sku",
                    "lot_numbers_tested": [],  # not exposed on this listing
                    "verified_at": snapshot_date,
                    "source_url": NSF_173_URL,
                    "evidence_band": "strong",
                    "product_form": fp.get("product_form"),
                    "facilities": facilities,
                }
            )

    print(f"NSF/ANSI 173: {company_count} companies → {len(records)} product records", file=sys.stderr)
    return records, snapshot_date


# ============================================================================
# NSF/ANSI 455-2 GMP (live) — info.nsf.org/Certified/455GMP/Listings.asp
# ============================================================================

NSF_455_GMP_URL = "https://info.nsf.org/Certified/455GMP/Listings.asp"
# 455-2 is the Dietary Supplements GMP standard (facility audit). 455-1 covers
# label claims; 455-3 the sport/banned-substance annex. We snapshot 455-2 only.
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
            while page_url:
                if max_pages is not None and page_count >= max_pages:
                    break
                print(f"GET {page_url}", file=sys.stderr)
                page.goto(page_url, wait_until="domcontentloaded", timeout=60_000)
                html = page.content()
                page_products, next_url = parse_usp_verified_listing_page(html, page.url)
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
    r.raise_for_status()
    r.encoding = "utf-8"
    products, listing_month = parse_informed_certified_products_page(r.text)

    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for row in products:
        brand = row["brand"]
        product = row["product"]
        key = (normalize_brand(brand), normalize_product(product))
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


def parse_nutrasource_products_payload(payload: dict) -> tuple[list[dict[str, str]], int]:
    """Parse the Nutrasource filtered-products JSON response.

    The endpoint includes product IDs and names, but not brand names. Brand is
    resolved from each product detail page before records are written.
    """
    total_count = int(payload.get("totalCount") or 0)
    rows: list[dict[str, str]] = []
    for item in payload.get("list", []) or []:
        if not item.get("IsIfos"):
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
        if "ifos" in cert_text:
            certifications.append("IFOS")

    return {
        "brand": brand,
        "product": product,
        "brand_id": brand_id_match.group(1) if brand_id_match else "",
        "certifications": certifications,
        "product_type": _clean_nutrasource_text(product_type_match.group(1)) if product_type_match else "",
        "source_url": f"{NUTRASOURCE_PRODUCT_DETAIL_URL}?id={product_num}",
    }


def fetch_ifos_live(max_products: int | None = None) -> tuple[list[dict], str]:
    """Fetch IFOS-certified products from Nutrasource.

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
            "forCertification": "IFOS",
            "forInterest": "",
            "forCategory": "",
            "byName": "",
        }
        print(f"GET {NUTRASOURCE_FILTERED_PRODUCTS_URL} page={page_number}", file=sys.stderr)
        r = requests.get(NUTRASOURCE_FILTERED_PRODUCTS_URL, params=params, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        payload = r.json()
        page_rows, total_count = parse_nutrasource_products_payload(payload)
        if not page_rows:
            break
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
        if total_count is not None and len(products) >= total_count:
            break
        page_number += 1

    print(f"IFOS: found {len(products)} product IDs (reported total {total_count})", file=sys.stderr)

    records: list[dict] = []
    seen_records: set[tuple[str, str]] = set()
    for i, row in enumerate(products, 1):
        product_num = row["product_num"]
        detail_url = f"{NUTRASOURCE_PRODUCT_DETAIL_URL}?id={product_num}"
        try:
            detail_response = requests.get(detail_url, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
            detail_response.raise_for_status()
            detail = parse_nutrasource_product_detail_page(detail_response.text, product_num)
        except requests.RequestException as exc:
            print(f"  detail fetch failed for {product_num}: {exc}", file=sys.stderr)
            detail = {}

        brand = str(detail.get("brand") or "").strip()
        product = str(detail.get("product") or row["product"]).strip()
        certifications = detail.get("certifications") or []
        if not brand or "IFOS" not in certifications:
            print(f"  skipping {product_num}: missing brand or IFOS detail certification", file=sys.stderr)
            continue

        key = (normalize_brand(brand), normalize_product(product))
        if key in seen_records:
            continue
        seen_records.add(key)
        record_id = _make_record_id("IFOS", brand, product, [], product_num)
        records.append(
            {
                "record_id": record_id,
                "program": "IFOS",
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

    print(f"IFOS: {len(records)} product records", file=sys.stderr)
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
    in many rows (one per tested lot). We group by (brand, product) and carry
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
        key = (normalize_brand(company), normalize_product(product))
        grp = groups.get(key)
        if grp is None:
            company_slug = str(item.get("company_slug") or "").strip()
            product_slug = str(item.get("product_slug") or "").strip()
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


def _load_existing_sources(exclude_programs: set[str]) -> list[dict]:
    """Return existing registry sources except programs being refreshed."""
    if not REGISTRY_PATH.exists():
        return []
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    source_by_program = {
        s.get("program"): s
        for s in payload.get("_metadata", {}).get("registry_sources", []) or []
        if s.get("program")
    }
    records_by_program: dict[str, list[dict]] = {}
    for record in payload.get("verified_records", []) or []:
        program = record.get("program")
        if not program or program in exclude_programs:
            continue
        records_by_program.setdefault(program, []).append(record)

    sources: list[dict] = []
    for program, records in records_by_program.items():
        source = source_by_program.get(program, {})
        sources.append(
            {
                "program": program,
                "url": source.get("url", records[0].get("source_url", "")),
                "snapshot_date": source.get("snapshot_date") or records[0].get("verified_at"),
                "records": records,
            }
        )
    return sources


def write_registry(sources_with_records: list[dict], merge_existing: bool = False) -> None:
    """Merge records from one or more sources into the registry file.

    Each element of sources_with_records is:
      {"program": "...", "url": "...", "snapshot_date": "YYYY-MM-DD", "records": [...]}
    """
    if merge_existing:
        refreshed_programs = {source["program"] for source in sources_with_records}
        sources_with_records = _load_existing_sources(refreshed_programs) + sources_with_records

    all_records: list[dict] = []
    registry_sources: list[dict] = []
    for source in sources_with_records:
        registry_sources.append(
            {
                "program": source["program"],
                "url": source["url"],
                "snapshot_date": source["snapshot_date"],
                "entry_count": len(source["records"]),
            }
        )
        all_records.extend(source["records"])

    payload = {
        "_metadata": {
            "schema_version": "6.0.0",
            "description": "Cached snapshots of public third-party certification registries.",
            "purpose": "cert_verification_v4",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "scoring_rule": (
                "Only verified_records with scope in {sku, product_line} AND recency_status in "
                "{fresh, warn} contribute B4a points. scoring_blocked records still appear in audits."
            ),
            "registry_sources": registry_sources,
            "total_verified_records": len(all_records),
        },
        "verified_records": all_records,
    }
    REGISTRY_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote registry to {REGISTRY_PATH} ({len(all_records)} records across {len(registry_sources)} programs)", file=sys.stderr)


# ============================================================================
# CLI
# ============================================================================


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
            "live-bscg",
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
    args = parser.parse_args()

    sources: list[dict] = []

    if args.source in ("live-nsf-sport", "all"):
        records, snapshot = fetch_nsf_sport_live(with_lots=args.with_lots)
        sources.append(
            {
                "program": "NSF Sport",
                "url": NSF_SPORT_SEARCH_URL,
                "snapshot_date": snapshot,
                "records": records,
            }
        )

    if args.source in ("live-nsf-173", "all"):
        records, snapshot = fetch_nsf_173_live()
        sources.append(
            {
                "program": "NSF Certified",
                "url": NSF_173_URL,
                "snapshot_date": snapshot,
                "records": records,
            }
        )

    if args.source in ("live-nsf-455", "all"):
        records, snapshot = fetch_nsf_455_live()
        sources.append(
            {
                "program": "NSF/ANSI 455",
                "url": f"{NSF_455_GMP_URL}?Standard={NSF_455_2_STANDARD}",
                "snapshot_date": snapshot,
                "records": records,
            }
        )

    if args.source in ("live-usp", "all"):
        records, snapshot = fetch_usp_verified_live(max_pages=args.max_pages)
        sources.append(
            {
                "program": "USP Verified",
                "url": USP_VERIFIED_URL,
                "snapshot_date": snapshot,
                "records": records,
            }
        )

    if args.source in ("live-informed-choice", "all"):
        records, snapshot = fetch_informed_live("Informed Choice")
        sources.append(
            {
                "program": "Informed Choice",
                "url": INFORMED_CHOICE_URL,
                "snapshot_date": snapshot,
                "records": records,
            }
        )

    if args.source in ("live-informed-sport", "all"):
        records, snapshot = fetch_informed_live("Informed Sport")
        sources.append(
            {
                "program": "Informed Sport",
                "url": INFORMED_SPORT_URL,
                "snapshot_date": snapshot,
                "records": records,
            }
        )

    if args.source in ("live-ifos", "all"):
        records, snapshot = fetch_ifos_live(max_products=args.max_pages)
        sources.append(
            {
                "program": "IFOS",
                "url": NUTRASOURCE_CERTIFIED_PRODUCTS_URL,
                "snapshot_date": snapshot,
                "records": records,
            }
        )

    if args.source in ("live-bscg", "all"):
        records, snapshot = fetch_bscg_live()
        sources.append(
            {
                "program": "BSCG",
                "url": BSCG_DATABASE_URL,
                "snapshot_date": snapshot,
                "records": records,
            }
        )

    if args.source == "pdf":
        if not args.pdf_path.exists():
            raise SystemExit(f"PDF not found at {args.pdf_path}")
        records, snapshot = fetch_nsf_sport_pdf(args.pdf_path)
        sources.append(
            {
                "program": "NSF Sport",
                "url": "https://info.nsf.org/Certified/NFL/DS-ABS_contacts.pdf",
                "snapshot_date": snapshot,
                "records": records,
            }
        )

    if args.dry_run:
        for s in sources:
            print(f"\n{s['program']} (snapshot {s['snapshot_date']}, {len(s['records'])} records)")
            for r in s["records"][:3]:
                print(json.dumps(r, indent=2, ensure_ascii=False))
        return

    write_registry(sources, merge_existing=args.merge_existing)


if __name__ == "__main__":
    main()
