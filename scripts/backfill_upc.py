#!/usr/bin/env python3
"""Backfill missing UPCs from UPCitemdb API.

Reads products with empty upc_sku from the staged JSON files,
searches UPCitemdb by brand + product name, and patches the JSON
when a high-confidence match is found.

Usage:
  # Trial mode (100 req/day, no key needed):
  python backfill_upc.py --mode trial --dry-run

  # Paid mode (uses your API key):
  python backfill_upc.py --mode paid --key YOUR_KEY

  # Apply changes (remove --dry-run):
  python backfill_upc.py --mode trial
"""

import argparse
import json
import glob
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from difflib import SequenceMatcher

# ── Config ────────────────────────────────────────────────────────────────────

STAGING_DIR = Path(__file__).parent.parent / "../../Documents/DataSetDsld/staging/brands"
# Resolve relative path — adjust if needed
if not STAGING_DIR.exists():
    STAGING_DIR = Path.home() / "Documents/DataSetDsld/staging/brands"

TRIAL_URL = "https://api.upcitemdb.com/prod/trial/search"
PAID_URL = "https://api.upcitemdb.com/prod/v1/search"

# Burst limit: 5 search requests per 30 seconds (trial)
BURST_WINDOW = 30
BURST_LIMIT = 5

REPORT_FILE = Path(__file__).parent / "backfill_upc_report.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def similarity(a: str, b: str) -> float:
    """Case-insensitive similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def clean_product_name(name: str) -> str:
    """Strip dosage/count info for better search matching."""
    # Remove patterns like "100 mg", "40ct", "60 Softgels", etc.
    cleaned = re.sub(r'\d+\s*(mg|mcg|iu|ct|count|softgels?|capsules?|tablets?|gummies?)\b',
                     '', name, flags=re.IGNORECASE)
    return cleaned.strip()


def search_upcitemdb(product_name: str, brand: str, mode: str, api_key: str = "") -> list:
    """Search UPCitemdb for a product by name and brand."""
    params = {
        "s": product_name,
        "brand": brand,
        "type": "product",
    }

    if mode == "trial":
        url = f"{TRIAL_URL}?{urllib.parse.urlencode(params)}"
        headers = {"User-Agent": "PharmaGuide/1.0"}
    else:
        url = f"{PAID_URL}?{urllib.parse.urlencode(params)}"
        headers = {
            "User-Agent": "PharmaGuide/1.0",
            "user_key": api_key,
            "key_type": "3scale",
        }

    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())

    if data.get("code") != "OK":
        return []

    return data.get("items", [])


def find_best_match(items, product_name, brand):
    """Find the best matching item from UPCitemdb results.

    Returns dict with upc, title, confidence or None.
    """
    if not items:
        return None

    best = None
    best_score = 0.0

    for item in items:
        upc = item.get("upc", "")
        title = item.get("title", "")
        item_brand = item.get("brand", "")

        if not upc or not re.match(r'^\d{12,13}$', upc):
            continue

        # Score: name similarity + brand match bonus
        name_sim = similarity(product_name, title)
        brand_sim = similarity(brand, item_brand) if item_brand else 0.3

        # Boost if product name words appear in title
        name_words = set(product_name.lower().split())
        title_lower = title.lower()
        word_hits = sum(1 for w in name_words if w in title_lower and len(w) > 2)
        word_ratio = word_hits / max(len(name_words), 1)

        score = (name_sim * 0.5) + (brand_sim * 0.3) + (word_ratio * 0.2)

        if score > best_score:
            best_score = score
            best = {
                "upc": upc,
                "title": title,
                "brand": item_brand,
                "confidence": round(score, 3),
            }

    # Only accept matches with confidence >= 0.45
    if best and best["confidence"] >= 0.45:
        return best
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Backfill missing UPCs from UPCitemdb")
    parser.add_argument("--mode", choices=["trial", "paid"], default="trial")
    parser.add_argument("--key", default="", help="API key for paid mode")
    parser.add_argument("--dry-run", action="store_true", help="Don't modify JSON files")
    parser.add_argument("--limit", type=int, default=95, help="Max API calls (default 95, safe under trial 100/day)")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N products (resume from where you left off)")
    parser.add_argument("--brand", default="", help="Only process products from this brand folder name")
    parser.add_argument("--db", default="", help="Path to built pharmaguide_core.db — only backfill products that are in the app DB")
    args = parser.parse_args()

    if args.mode == "paid" and not args.key:
        print("ERROR: --key required for paid mode")
        sys.exit(1)

    # If --db is provided, only target products that are in the built DB with missing UPCs
    db_dsld_ids = None
    if args.db:
        import sqlite3
        conn = sqlite3.connect(args.db)
        rows = conn.execute(
            "SELECT dsld_id, product_name, brand_name FROM products_core "
            "WHERE upc_sku IS NULL OR TRIM(upc_sku) = ''"
        ).fetchall()
        db_dsld_ids = {str(r[0]) for r in rows}
        conn.close()
        print(f"DB filter: {len(db_dsld_ids)} products in app DB need UPCs")

    # Collect all products with missing UPCs from staged JSON files
    if args.brand:
        pattern = str(STAGING_DIR / args.brand / "*.json")
    else:
        pattern = str(STAGING_DIR / "*/*.json")
    json_files = sorted(glob.glob(pattern))
    missing = []

    for f in json_files:
        try:
            d = json.load(open(f))
            upc = d.get("upcSku", "")
            if not str(upc).strip():
                name = d.get("fullName") or d.get("product_name") or ""
                brand = d.get("brandName") or ""
                dsld_id = str(d.get("dsld_id") or d.get("id") or Path(f).stem)
                if name and brand:
                    # If --db filter is active, skip products not in the built DB
                    if db_dsld_ids is not None and dsld_id not in db_dsld_ids:
                        continue
                    missing.append({
                        "file": f,
                        "dsld_id": dsld_id,
                        "name": name,
                        "brand": brand,
                    })
        except (json.JSONDecodeError, KeyError):
            pass

    total_missing = len(missing)
    if args.offset > 0:
        missing = missing[args.offset:]

    print(f"Found {total_missing} products to backfill (processing from offset {args.offset})")
    print(f"API mode: {args.mode} | Limit: {args.limit} calls | Dry run: {args.dry_run}")
    if args.brand:
        print(f"Brand filter: {args.brand}")
    print("-" * 70)

    results = {
        "matched": [],
        "not_found": [],
        "low_confidence": [],
        "errors": [],
    }

    request_count = 0
    burst_count = 0
    burst_start = time.time()

    for i, product in enumerate(missing):
        if request_count >= args.limit:
            print(f"\n[LIMIT] Reached {args.limit} API calls. Run again tomorrow for more.")
            break

        # Burst rate limiting
        burst_count += 1
        if burst_count >= BURST_LIMIT:
            elapsed = time.time() - burst_start
            if elapsed < BURST_WINDOW:
                wait = BURST_WINDOW - elapsed + 1
                print(f"  [rate limit] waiting {wait:.0f}s...")
                time.sleep(wait)
            burst_count = 0
            burst_start = time.time()

        name = product["name"]
        brand = product["brand"]
        dsld_id = product["dsld_id"]

        print(f"[{i+1}/{len(missing)}] {brand} — {name} (dsld_id={dsld_id})")

        try:
            items = search_upcitemdb(name, brand, args.mode, args.key)
            request_count += 1

            match = find_best_match(items, name, brand)

            if match:
                conf = match["confidence"]
                label = "HIGH" if conf >= 0.65 else "MED"

                print(f"  [{label} {conf}] UPC={match['upc']}  →  {match['title']}")

                if conf >= 0.65:
                    results["matched"].append({**product, "match": match})

                    if not args.dry_run:
                        # Patch the JSON file
                        d = json.load(open(product["file"]))
                        d["upcSku"] = match["upc"]
                        with open(product["file"], "w") as out:
                            json.dump(d, out, indent=2, ensure_ascii=False)
                        print(f"  ✓ Patched {Path(product['file']).name}")
                else:
                    results["low_confidence"].append({**product, "match": match})
                    print(f"  ⚠ Low confidence — skipped (review manually)")
            else:
                results["not_found"].append(product)
                print(f"  ✗ No match")

        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  [429] Rate limited. Waiting 35s...")
                time.sleep(35)
                burst_count = 0
                burst_start = time.time()
                # Retry once
                try:
                    items = search_upcitemdb(name, brand, args.mode, args.key)
                    request_count += 1
                    match = find_best_match(items, name, brand)
                    if match and match["confidence"] >= 0.65:
                        results["matched"].append({**product, "match": match})
                        if not args.dry_run:
                            d = json.load(open(product["file"]))
                            d["upcSku"] = match["upc"]
                            with open(product["file"], "w") as out:
                                json.dump(d, out, indent=2, ensure_ascii=False)
                        print(f"  ✓ Retry matched: {match['upc']}")
                    else:
                        results["not_found"].append(product)
                except Exception:
                    results["errors"].append({**product, "error": "retry failed"})
            else:
                results["errors"].append({**product, "error": str(e)})
                print(f"  ERROR: {e}")
        except Exception as e:
            results["errors"].append({**product, "error": str(e)})
            print(f"  ERROR: {e}")

    # Summary
    print("\n" + "=" * 70)
    print(f"DONE — {request_count} API calls used")
    print(f"  Matched (high confidence): {len(results['matched'])}")
    print(f"  Low confidence (skipped):  {len(results['low_confidence'])}")
    print(f"  Not found:                 {len(results['not_found'])}")
    print(f"  Errors:                    {len(results['errors'])}")
    print(f"  Remaining:                 {len(missing) - request_count}")

    # Save report
    report = {
        "api_calls": request_count,
        "mode": args.mode,
        "dry_run": args.dry_run,
        **{k: len(v) for k, v in results.items()},
        "low_confidence_review": [
            {
                "dsld_id": p["dsld_id"],
                "name": p["name"],
                "brand": p["brand"],
                "suggested_upc": p["match"]["upc"],
                "suggested_title": p["match"]["title"],
                "confidence": p["match"]["confidence"],
            }
            for p in results["low_confidence"]
        ],
        "matched_summary": [
            {
                "dsld_id": p["dsld_id"],
                "name": p["name"],
                "upc": p["match"]["upc"],
                "confidence": p["match"]["confidence"],
            }
            for p in results["matched"]
        ],
    }

    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {REPORT_FILE}")


if __name__ == "__main__":
    main()
