#!/usr/bin/env python3
"""Row-level OCR of a Supplement Facts panel from an archived DSLD label PDF.

The archived label images are scans, so the distinction that matters for the E2
unit cases (``mcg`` vs ``mg``) is a single glyph. Whole-page OCR is not reliable
enough; this tool uses tesseract's own word boxes to locate the Supplement Facts
panel rows and re-OCRs each row band at 6x magnification with an alphanumeric
whitelist, which reads unit glyphs consistently.

Images are piped to tesseract **on stdin** — tesseract's file reader is
intermittently blocked on macOS for scratch paths, and stdin removes that
dependency entirely. Nothing is written except optional crops, and the tool
never touches a product lane or the frozen corpus.

Usage:
  label_row_ocr_20260920.py --pdf 231334.pdf --rows "Vitamin A,Vitamin E"
  label_row_ocr_20260920.py --pdf 231334.pdf --rows "Vitamin A" --panel-x 1600
"""
from __future__ import annotations

import argparse
import csv
import io
import subprocess
import sys
from pathlib import Path

import fitz
from PIL import Image, ImageOps

WHITELIST = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,.<>()%/"


def run_tesseract(img_bytes: bytes, *extra: str) -> str:
    res = subprocess.run(
        ["tesseract", "-", "stdout", *extra],
        input=img_bytes, capture_output=True, text=False, timeout=300,
    )
    return res.stdout.decode("utf-8", "replace")


def png_bytes(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def render(pdf: Path, dpi: int = 400) -> Image.Image:
    doc = fitz.open(pdf)
    pix = doc[0].get_pixmap(dpi=dpi)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    return im


def tsv_words(im: Image.Image) -> list[dict]:
    out = run_tesseract(png_bytes(im), "--psm", "6", "-l", "eng", "tsv")
    return [w for w in csv.DictReader(io.StringIO(out), delimiter="\t") if w.get("text")]


def ocr_letters(im: Image.Image, psm: int) -> str:
    out = run_tesseract(png_bytes(im), "--psm", str(psm), "-l", "eng",
                        "-c", f"tessedit_char_whitelist={WHITELIST}0123456789")
    return out.strip().replace("\n", " ")


def panel_x(words: list[dict]) -> int:
    if not words:
        return 0
    maxx = max(int(w["left"]) + int(w["width"]) for w in words)
    return int(maxx * 0.55)


def find_row(words: list[dict], target: str, x0: int) -> dict | None:
    want = [t for t in target.split() if t]
    ordered = sorted((w for w in words if int(w["left"]) >= x0),
                     key=lambda w: (int(w["top"]), int(w["left"])))
    for i in range(len(ordered) - len(want) + 1):
        seq = ordered[i:i + len(want)]
        if not all(abs(int(a["top"]) - int(b["top"])) <= 10
                   for a, b in zip(seq, seq[1:])):
            continue
        ok = True
        for j in range(len(want)):
            a = want[j].lower().strip(":.")
            b = (seq[j]["text"] or "").lower().strip(":.")
            if a != b:
                ok = False
                break
        if ok:
            return seq[0]
    return None


def read_row(words: list[dict], img: Image.Image, target: str, x0: int,
             scale: int = 6, pad: int = 4) -> dict | None:
    anchor = find_row(words, target, x0)
    if anchor is None:
        return None
    top = int(anchor["top"])
    band = [x for x in words
            if int(x["left"]) >= x0 and abs(int(x["top"]) - top) <= 14]
    left = min(int(x["left"]) for x in band) - pad
    right = max(int(x["left"]) + int(x["width"]) for x in band) + pad
    h = int(anchor["height"])
    box = (max(0, left), max(0, top - pad - h // 2),
           min(img.width, right), min(img.height, top + h + h // 2))
    crop = img.crop(box).convert("L")
    crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
    crop = ImageOps.autocontrast(crop)
    # A second, tighter crop around just the unit/quantity zone is a useful
    # cross-check when the wholesale row read is ambiguous.
    return {
        "target": target,
        "box": box,
        "tokens": " ".join(x["text"] for x in sorted(band, key=lambda y: int(y["left"]))),
        "psm7": ocr_letters(crop, 7),
        "psm6": ocr_letters(crop, 6),
        "_crop": crop,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--rows", required=True, help="comma-separated row labels")
    ap.add_argument("--dpi", type=int, default=400)
    ap.add_argument("--scale", type=int, default=6)
    ap.add_argument("--panel-x", type=int, default=None)
    ap.add_argument("--dump-crop", default=None)
    args = ap.parse_args()

    img = render(Path(args.pdf), args.dpi)
    words = tsv_words(img)
    x0 = args.panel_x if args.panel_x is not None else panel_x(words)
    print(f"# {args.pdf} → {img.width}x{img.height}, words={len(words)}, panel x0={x0}")
    for target in [t.strip() for t in args.rows.split(",") if t.strip()]:
        r = read_row(words, img, target, x0, args.scale)
        if not r:
            print(f"\n[{target}] not found in panel")
            continue
        print(f"\n[{target}]  box={r['box']}")
        print(f"  raw tokens : {r['tokens'][:200]}")
        print(f"  ocr psm7   : {r['psm7']}")
        print(f"  ocr psm6   : {r['psm6']}")
        if args.dump_crop:
            Path(args.dump_crop).mkdir(parents=True, exist_ok=True)
            r["_crop"].save(Path(args.dump_crop) / f"{Path(args.pdf).stem}__{target.replace(' ','_')}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
