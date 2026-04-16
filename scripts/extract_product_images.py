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
MAX_CONCURRENT_DOWNLOADS = 5
BATCH_DELAY_SECONDS = 0.5
WEBP_QUALITY = 80
MAX_WIDTH_PX = 600

# ---------------------------------------------------------------------------
# PDF download
# ---------------------------------------------------------------------------


def ensure_cache_dir():
    os.makedirs(PDF_CACHE_DIR, exist_ok=True)


def cached_pdf_path(dsld_id: str) -> str:
    return os.path.join(PDF_CACHE_DIR, f"{dsld_id}.pdf")


def download_pdf(dsld_id: str, url: str) -> str:
    """Download PDF to cache. Returns path on success, raises on failure."""
    import requests

    dest = cached_pdf_path(dsld_id)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest


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

    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        # Render at 2x for quality, then downscale
        zoom = 2.0
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


def process_one(dsld_id: str, image_url: str, output_dir: str) -> dict:
    """Download PDF → extract thumbnail → return index entry or error."""
    webp_path = os.path.join(output_dir, f"{dsld_id}.webp")

    # Already exists — skip
    if os.path.exists(webp_path) and os.path.getsize(webp_path) > 0:
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
) -> dict:
    """Main extraction loop. Returns summary dict."""
    ensure_cache_dir()
    os.makedirs(output_dir, exist_ok=True)

    products = load_products_from_db(db_path)
    total = len(products)
    logger.info("Found %d products with PDF image URLs", total)

    index = {}
    downloaded = 0
    skipped = 0
    failed = 0
    errors = []

    # Process in batches of max_workers with delay between batches
    start = time.time()
    batch_num = 0

    for batch_start in range(0, total, max_workers):
        batch = products[batch_start : batch_start + max_workers]
        batch_num += 1

        if batch_num > 1:
            time.sleep(batch_delay)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_one, dsld_id, url, output_dir): dsld_id
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
        if processed % 100 < max_workers or batch_start + max_workers >= total:
            elapsed = time.time() - start
            logger.info(
                "Progress: %d/%d (downloaded=%d, skipped=%d, failed=%d) %.1fs",
                processed, total, downloaded, skipped, failed, elapsed,
            )

    # Write index
    index_path = os.path.join(output_dir, "product_image_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, sort_keys=True)

    elapsed = time.time() - start

    summary = {
        "total": total,
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "index_entries": len(index),
        "elapsed_seconds": round(elapsed, 1),
    }

    print(f"\n{'=' * 50}")
    print(f"Image Extraction Summary")
    print(f"  Total products:  {total}")
    print(f"  Downloaded:      {downloaded}")
    print(f"  Skipped (exist): {skipped}")
    print(f"  Failed:          {failed}")
    print(f"  Index entries:   {len(index)}")
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
        required=True,
        help="Directory to write .webp thumbnails and index JSON",
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
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if not os.path.exists(args.db_path):
        print(f"Error: DB not found: {args.db_path}")
        sys.exit(1)

    run_extraction(
        db_path=args.db_path,
        output_dir=args.output_dir,
        max_workers=args.max_workers,
        batch_delay=args.batch_delay,
    )


if __name__ == "__main__":
    main()
