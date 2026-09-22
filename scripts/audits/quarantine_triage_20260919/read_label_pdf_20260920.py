#!/usr/bin/env python3
"""Printed-label OCR reader for the Phase-3 source-resolution phase (2026-09-20).

The DSLD label images are *scanned* PDFs with no text layer, so structured-field
ambiguity cannot be settled by ``pdftotext``. This tool renders the archived
label PDF for a DSLD id at high DPI and OCRs it, so every correction receipt can
cite the **printed** label rather than a plausibility argument.

Provenance is preserved per label:
  * the exact source URL (NIH DSLD S3 label store),
  * the SHA-256 of the downloaded PDF,
  * the DPI and page count,
  * the OCR engine/version.

Images are intentionally NOT committed (multi-MB corpora). The extracted text,
the source URL and the PDF hash are, so the reading is reproducible from the URL.

Usage:
  read_label_pdf_20260920.py --ids 269360,231334 --out <dir>
  read_label_pdf_20260920.py --ids all --force
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PDF_URL = "https://api.ods.od.nih.gov/dsld/s3/pdf/{dsld_id}.pdf"
HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "source_resolution_20260920" / "labels"
DPI = 300


def ocr_bin() -> str:
    exe = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"
    if not Path(exe).exists():
        raise SystemExit("tesseract not found")
    return exe


def download(pid: str, dest: Path) -> tuple[str, int]:
    req = urllib.request.Request(PDF_URL.format(dsld_id=pid), headers={"User-Agent": "PG/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        blob = resp.read()
    dest.write_bytes(blob)
    return hashlib.sha256(blob).hexdigest(), len(blob)


def render_and_ocr(pid: str, pdf_path: Path, outdir: Path, dpi: int) -> dict:
    import fitz  # PyMuPDF

    import PIL.Image  # noqa: F401  (ensures Pillow present for tesseract handoff)

    doc = fitz.open(pdf_path)
    pages_text: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        for idx, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            png = Path(td) / f"p{idx}.png"
            pix.save(png)
            res = subprocess.run(
                [ocr_bin(), str(png), "stdout", "--psm", "6"],
                capture_output=True, text=True, timeout=300,
            )
            pages_text.append(res.stdout)
        pages = doc.page_count
    doc.close()
    text = "\n\n===== PAGE BREAK =====\n\n".join(pages_text)
    (outdir / f"{pid}.ocr.txt").write_text(text, encoding="utf-8")
    return {"pages": pages, "ocr_chars": len(text)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="all")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dpi", type=int, default=DPI)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--index", default=None, help="id list source (live_source_index json)")
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    if args.ids.strip() == "all":
        idx = json.loads((Path(args.index) if args.index else
                          HERE / "source_resolution_20260920" / "live_source_index_20260920.json"
                          ).read_text())
        ids = sorted(idx.keys())
    else:
        ids = [s.strip() for s in args.ids.split(",") if s.strip()]

    manifest_path = outdir / "label_ocr_manifest_20260920.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    scratch = Path(tempfile.mkdtemp(prefix="pg_labels_"))

    for pid in ids:
        entry = manifest.get(pid, {})
        txt = outdir / f"{pid}.ocr.txt"
        if txt.exists() and not args.force:
            print(f"{pid}: cached ({txt.stat().st_size} chars)")
            continue
        try:
            pdf = scratch / f"{pid}.pdf"
            sha, size = download(pid, pdf)
            meta = render_and_ocr(pid, pdf, outdir, args.dpi)
            entry.update({
                "dsld_id": pid, "source_url": PDF_URL.format(dsld_id=pid),
                "pdf_sha256": sha, "pdf_bytes": size, "dpi": args.dpi,
                "pages": meta["pages"], "ocr_chars": meta["ocr_chars"],
                "ocr_engine": f"tesseract {subprocess.run([ocr_bin(),'--version'],capture_output=True,text=True).stdout.splitlines()[0]}",
                "retrieved_at_utc": retrieved_at,
                "text_file": str(txt.relative_to(HERE)),
            })
            print(f"{pid}: {meta['pages']} page(s), {meta['ocr_chars']} chars, sha={sha[:16]}")
        except Exception as exc:  # noqa: BLE001
            entry.update({"dsld_id": pid, "error": f"{type(exc).__name__}: {exc}",
                          "retrieved_at_utc": retrieved_at})
            print(f"{pid}: FAILED — {entry['error']}")
            sys.stdout.flush()
        manifest[pid] = entry
        manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")

    shutil.rmtree(scratch, ignore_errors=True)
    print(f"\nmanifest -> {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
