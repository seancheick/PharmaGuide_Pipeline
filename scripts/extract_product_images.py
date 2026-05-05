#!/usr/bin/env python3
"""Extract product label thumbnails from DSLD PDF URLs.

Reads pharmaguide_core.db, downloads each product's label PDF,
renders page 1 at full size (no cropping), and converts to WebP.

These serve as fallback images when Open Food Facts has no photo.

Usage:
    python scripts/extract_product_images.py \
        --db-path scripts/dist/pharmaguide_core.db \
        --output-dir scripts/dist/product_images

Dependencies: PyMuPDF (fitz), Pillow
"""

import argparse
import hashlib
import io
import json
import logging
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PDF_CACHE_DIR = "/tmp/dsld_pdf_cache"
MAX_CONCURRENT_DOWNLOADS = 2
BATCH_DELAY_SECONDS = 1.5

# ─────────────────────────────────────────────────────────────────────────
# IMAGE QUALITY KNOBS — tweak these, then rerun with --force-rerender
# Full guide: scripts/PIPELINE_OPERATIONS_README.md § 6A
# ─────────────────────────────────────────────────────────────────────────

# WebP encoder quality (0-100). Dominant text-edge sharpness knob.
#   80 = soft text, smaller files
#   85 = balanced
#   88 = sharp text edges (current)
#   92+ = diminishing returns, ~25% bigger files
# File-size impact: ~+10% per +3 quality points.
WEBP_QUALITY = 88

# Output width in pixels. Aspect ratio is preserved. DOMINANT FILE-SIZE DRIVER.
#   600  ≈ 25 KB/img,  ~200 MB total — too soft on retina screens
#   900  ≈ 80 KB/img,  ~640 MB total (current) — sharp on phone
#   1200 ≈ 140 KB/img, ~1.1 GB total — overkill for thumbnails
# File-size impact: scales linearly with pixel count (width × height).
MAX_WIDTH_PX = 900

# Multiplier for PDF source render before LANCZOS downscale. NEAR ZERO file-size impact.
#   2.0 = 144 DPI source — visibly blurry
#   4.0 = 288 DPI — readable
#   8.0 = 576 DPI (current) — sharp
#   10+ = diminishing returns; baked-in raster scans cap the ceiling
# Bump this freely — final WebP size is fixed by MAX_WIDTH_PX, not zoom.
# Speed impact: zoom 8 ≈ 4× slower per render than zoom 4 (NIH download still bottleneck).
RENDER_ZOOM = 8.0

# Safety cap on raw source bitmap before LANCZOS downscale.
# Some DSLD label PDFs are oversized panels that, at zoom=8, would produce
# 1-2+ billion-pixel raw bitmaps (6+ GB RAM each, > PIL's hard limit).
# When a render would exceed this, zoom is automatically scaled down so the
# source bitmap fits in this budget. Final WebP output is still at MAX_WIDTH_PX.
# 150M pixels ≈ 600 MB raw RGB; safe on any modern machine.
MAX_SOURCE_PIXELS = 150_000_000

# Retry / rate-limit handling
HTTP_USER_AGENT = "PharmaGuide-DataPipeline/1.0 (+https://github.com/seancheick/dsld_clean)"
HTTP_TIMEOUT_SECONDS = 30
MAX_RETRIES = 4
RETRY_BACKOFF_BASE_SECONDS = 5  # 5s, 15s, 45s, 135s
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# ---------------------------------------------------------------------------
# PDF download
# ---------------------------------------------------------------------------


def ensure_cache_dir():
    os.makedirs(PDF_CACHE_DIR, exist_ok=True)


def cached_pdf_path(dsld_id: str) -> str:
    return os.path.join(PDF_CACHE_DIR, f"{dsld_id}.pdf")


def download_pdf(dsld_id: str, url: str) -> str:
    """Download PDF to cache with retry/backoff. Returns path on success, raises on failure."""
    import requests

    dest = cached_pdf_path(dsld_id)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest

    headers = {"User-Agent": HTTP_USER_AGENT}
    last_exc = None

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS, headers=headers)

            if resp.status_code in RETRYABLE_STATUS_CODES:
                # Honor Retry-After header if present (seconds form), else exponential backoff
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    sleep_for = int(retry_after)
                else:
                    sleep_for = RETRY_BACKOFF_BASE_SECONDS * (3 ** attempt)
                if attempt < MAX_RETRIES - 1:
                    logger.info("HTTP %d on %s, retrying in %ds (attempt %d/%d)",
                                resp.status_code, dsld_id, sleep_for, attempt + 1, MAX_RETRIES)
                    time.sleep(sleep_for)
                    continue
                resp.raise_for_status()  # final attempt — raise

            resp.raise_for_status()

            # Atomic write: temp file + rename to avoid corrupt cache on interrupt
            tmp_dest = dest + ".tmp"
            with open(tmp_dest, "wb") as f:
                f.write(resp.content)
            os.replace(tmp_dest, dest)
            return dest

        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                sleep_for = RETRY_BACKOFF_BASE_SECONDS * (3 ** attempt)
                logger.info("Network error on %s: %s — retrying in %ds (attempt %d/%d)",
                            dsld_id, exc, sleep_for, attempt + 1, MAX_RETRIES)
                time.sleep(sleep_for)
                continue
            raise

    # Should be unreachable, but be defensive
    raise last_exc if last_exc else RuntimeError(f"download_pdf exhausted retries for {dsld_id}")


# ---------------------------------------------------------------------------
# PDF → WebP conversion (NO cropping — full page render)
# ---------------------------------------------------------------------------


def pdf_page1_to_webp(pdf_path: str, output_path: str) -> int:
    """Render page 1 of a PDF, resize to max width, save as WebP.

    No cropping — the full label page is preserved as-is.
    Returns file size in bytes.
    """
    import fitz  # PyMuPDF
    from PIL import Image

    # We trust the input source (NIH DSLD PDFs). Disable PIL's DoS check.
    # Without this, oversized DSLD label panels trigger DecompressionBombError.
    Image.MAX_IMAGE_PIXELS = None

    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        # Compute a safe zoom: cap source bitmap at MAX_SOURCE_PIXELS so we
        # never allocate multi-GB raw images for outlier PDFs (some DSLD
        # label panels at zoom=8 would produce >2 billion pixels = ~6 GB RAM).
        rect = page.rect  # in points
        page_w_pt = max(1.0, rect.width)
        page_h_pt = max(1.0, rect.height)
        full_pixels = (page_w_pt * RENDER_ZOOM) * (page_h_pt * RENDER_ZOOM)
        if full_pixels > MAX_SOURCE_PIXELS:
            # Scale zoom down so source = MAX_SOURCE_PIXELS exactly
            scale = (MAX_SOURCE_PIXELS / full_pixels) ** 0.5
            zoom = RENDER_ZOOM * scale
        else:
            zoom = RENDER_ZOOM
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_data = pix.tobytes("png")
    finally:
        doc.close()

    img = Image.open(io.BytesIO(img_data))

    # Resize to max width (preserve aspect ratio)
    if img.width > MAX_WIDTH_PX:
        ratio = MAX_WIDTH_PX / img.width
        new_h = int(img.height * ratio)
        img = img.resize((MAX_WIDTH_PX, new_h), Image.LANCZOS)

    # Convert to RGB if needed (PDF pages can have odd modes)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "WEBP", quality=WEBP_QUALITY)
    return os.path.getsize(output_path)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Single-product pipeline
# ---------------------------------------------------------------------------


def process_one(dsld_id: str, image_url: str, output_dir: str,
                force_rerender: bool = False) -> dict:
    """Download PDF → extract thumbnail → return index entry or error."""
    webp_path = os.path.join(output_dir, f"{dsld_id}.webp")

    # Already exists — skip (unless force_rerender)
    if (not force_rerender
            and os.path.exists(webp_path)
            and os.path.getsize(webp_path) > 0):
        return {"status": "skipped", "dsld_id": dsld_id}

    try:
        pdf_path = download_pdf(dsld_id, image_url)
        size_bytes = pdf_page1_to_webp(pdf_path, webp_path)
        sha = file_sha256(webp_path)
        return {
            "status": "ok",
            "dsld_id": dsld_id,
            "filename": f"{dsld_id}.webp",
            "size_bytes": size_bytes,
            "sha256": sha,
        }
    except Exception as exc:
        logger.warning("Failed %s: %s", dsld_id, exc)
        return {"status": "failed", "dsld_id": dsld_id, "error": str(exc)}


# ---------------------------------------------------------------------------
# Batch orchestration
# ---------------------------------------------------------------------------


def load_products_from_db(db_path: str) -> list[tuple[str, str]]:
    """Return list of (dsld_id, image_url) where image_url ends in .pdf."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT dsld_id, image_url FROM products_core "
            "WHERE image_url IS NOT NULL AND image_url != '' "
            "AND LOWER(image_url) LIKE '%.pdf'"
        ).fetchall()
    finally:
        conn.close()
    return rows


def run_extraction(
    db_path: str,
    output_dir: str,
    max_workers: int = MAX_CONCURRENT_DOWNLOADS,
    batch_delay: float = BATCH_DELAY_SECONDS,
    force_rerender: bool = False,
) -> dict:
    """Main extraction loop. Returns summary dict.

    force_rerender: when True, ignore existing .webp files and regenerate
    them. PDF cache is still reused (skips re-download), only the render
    step runs again.
    """
    ensure_cache_dir()
    os.makedirs(output_dir, exist_ok=True)

    all_products = load_products_from_db(db_path)
    total = len(all_products)
    logger.info("Found %d products with PDF image URLs", total)
    if force_rerender:
        logger.info("--force-rerender enabled: existing .webp files will be regenerated")

    index = {}
    downloaded = 0
    skipped = 0
    failed = 0
    errors = []

    # ── Pre-filter: separate already-done from work-to-do ──
    # The batch_delay (1.5s) was firing between every batch even when all
    # entries were skip-on-disk-exists. With 3,991 batches that's ~100 min
    # of pure sleep. Pre-filtering means the rate-limit delay only applies
    # to batches that actually hit the network.
    pending = []
    pre_skip_start = time.time()
    for dsld_id, url in all_products:
        webp_path = os.path.join(output_dir, f"{dsld_id}.webp")
        if (not force_rerender
                and os.path.exists(webp_path)
                and os.path.getsize(webp_path) > 0):
            skipped += 1
            index[dsld_id] = {
                "filename": f"{dsld_id}.webp",
                "size_bytes": os.path.getsize(webp_path),
                "sha256": file_sha256(webp_path),
            }
        else:
            pending.append((dsld_id, url))

    pre_skip_elapsed = time.time() - pre_skip_start
    logger.info(
        "Pre-scan: %d already done (skipped), %d to download. (%.1fs)",
        skipped, len(pending), pre_skip_elapsed,
    )

    # Process pending in batches of max_workers with delay between batches
    start = time.time()
    batch_num = 0
    pending_total = len(pending)

    for batch_start in range(0, pending_total, max_workers):
        batch = pending[batch_start : batch_start + max_workers]
        batch_num += 1

        if batch_num > 1:
            time.sleep(batch_delay)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_one, dsld_id, url, output_dir, force_rerender): dsld_id
                for dsld_id, url in batch
            }
            for future in as_completed(futures):
                result = future.result()
                dsld_id = result["dsld_id"]

                if result["status"] == "ok":
                    downloaded += 1
                    index[dsld_id] = {
                        "filename": result["filename"],
                        "size_bytes": result["size_bytes"],
                        "sha256": result["sha256"],
                    }
                elif result["status"] == "skipped":
                    skipped += 1
                    # Rebuild index entry for already-existing file
                    webp_path = os.path.join(output_dir, f"{dsld_id}.webp")
                    if os.path.exists(webp_path):
                        index[dsld_id] = {
                            "filename": f"{dsld_id}.webp",
                            "size_bytes": os.path.getsize(webp_path),
                            "sha256": file_sha256(webp_path),
                        }
                else:
                    failed += 1
                    errors.append(result)

        processed = downloaded + skipped + failed
        if processed % 100 < max_workers or batch_start + max_workers >= pending_total:
            elapsed = time.time() - start
            logger.info(
                "Progress: %d/%d (downloaded=%d, skipped=%d, failed=%d) %.1fs",
                processed, total, downloaded, skipped, failed, elapsed,
            )

    # Write index
    index_path = os.path.join(output_dir, "product_image_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, sort_keys=True)

    backfill = backfill_image_thumbnail_urls(db_path, output_dir, index)
    manifest_update = refresh_export_manifest_checksum(db_path)

    elapsed = time.time() - start

    summary = {
        "total": total,
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "index_entries": len(index),
        "thumbnail_urls_updated": backfill["updated"],
        "manifest_checksum_updated": manifest_update["updated"],
        "elapsed_seconds": round(elapsed, 1),
    }

    print(f"\n{'=' * 50}")
    print(f"Image Extraction Summary")
    print(f"  Total products:  {total}")
    print(f"  Downloaded:      {downloaded}")
    print(f"  Skipped (exist): {skipped}")
    print(f"  Failed:          {failed}")
    print(f"  Index entries:   {len(index)}")
    print(f"  DB thumbnails:   {backfill['updated']} updated")
    print(f"  Manifest:        {'checksum updated' if manifest_update['updated'] else 'not found'}")
    print(f"  Time:            {elapsed:.1f}s")
    print(f"  Output:          {output_dir}")
    print(f"  Index:           {index_path}")
    print(f"{'=' * 50}")

    if errors:
        print(f"\nFailed products ({len(errors)}):")
        for err in errors[:20]:
            print(f"  {err['dsld_id']}: {err['error']}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")

    return summary


def default_output_dir_for_db(db_path: str) -> str:
    """Default to a product_images folder next to the core DB."""
    return os.path.join(os.path.dirname(os.path.abspath(db_path)), "product_images")


def backfill_image_thumbnail_urls(db_path: str, image_dir: str, index: dict) -> dict:
    """Populate products_core.image_thumbnail_url for extracted thumbnails.

    The value intentionally includes the Supabase bucket prefix for compatibility
    with the v1.4.0 export schema (`product-images/{dsld_id}.webp`). Flutter
    normalizes this to an object key before building the public URL.
    """
    updated = 0
    conn = sqlite3.connect(db_path)
    try:
        for dsld_id, entry in index.items():
            filename = entry.get("filename") or f"{dsld_id}.webp"
            webp_path = os.path.join(image_dir, filename)
            if not os.path.exists(webp_path) or os.path.getsize(webp_path) <= 0:
                continue
            conn.execute(
                "UPDATE products_core SET image_thumbnail_url = ? WHERE dsld_id = ?",
                (f"product-images/{filename}", str(dsld_id)),
            )
            updated += 1
        conn.commit()
    finally:
        conn.close()
    return {"updated": updated, "missing": len(index) - updated}


def refresh_export_manifest_checksum(db_path: str) -> dict:
    """Refresh export_manifest checksum after in-place DB thumbnail backfill."""
    manifest_path = os.path.join(os.path.dirname(os.path.abspath(db_path)), "export_manifest.json")
    if not os.path.exists(manifest_path):
        return {"updated": False}

    digest = file_sha256(db_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["checksum"] = f"sha256:{digest}"
    manifest["checksum_sha256"] = digest
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return {"updated": True, "checksum": f"sha256:{digest}"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Extract product label thumbnails from DSLD PDF URLs."
    )
    parser.add_argument(
        "--db-path",
        required=True,
        help="Path to pharmaguide_core.db",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write .webp thumbnails and index JSON "
             "(default: <db-dir>/product_images)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=MAX_CONCURRENT_DOWNLOADS,
        help=f"Max concurrent downloads (default: {MAX_CONCURRENT_DOWNLOADS})",
    )
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=BATCH_DELAY_SECONDS,
        help=f"Seconds between download batches (default: {BATCH_DELAY_SECONDS})",
    )
    parser.add_argument(
        "--force-rerender",
        action="store_true",
        help="Regenerate all .webp files even if they already exist. "
             "PDF cache is reused, only the render+resize+encode step runs again.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if not os.path.exists(args.db_path):
        print(f"Error: DB not found: {args.db_path}")
        sys.exit(1)

    output_dir = args.output_dir or default_output_dir_for_db(args.db_path)

    run_extraction(
        db_path=args.db_path,
        output_dir=output_dir,
        max_workers=args.max_workers,
        batch_delay=args.batch_delay,
        force_rerender=args.force_rerender,
    )


if __name__ == "__main__":
    main()
