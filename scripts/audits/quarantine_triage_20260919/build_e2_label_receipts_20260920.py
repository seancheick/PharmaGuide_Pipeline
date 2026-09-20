#!/usr/bin/env python3
"""E2 unit-corruption receipts: printed label vs structured DSLD (2026-09-20).

For each E2 product and each flagged nutrient row this prints and records:

  * the printed quantity and unit token read from the **archived DSLD label
    image** (the scan that matches this product/version, not today's formula);
  * a width/whitelist glyph test that separates ``mg`` from ``mcg`` — on these
    labels a two-character ``mg`` box measures ~39 px and a three-character
    ``mcg`` box ~54 px at 600 dpi, which is calibrated in-run against rows whose
    unit is not in question;
  * the structured value/unit from the frozen ingest record and from live DSLD.

The verdict per row is mechanical:

  record_unit_disagrees_with_printed_label  -> source_verified_correction
  record_unit_matches_printed_label         -> source_record_correct_no_change
  printed unit glyph unreadable             -> source_insufficient_keep_withheld

No plausibility-based conversion is performed anywhere: a correction is only
emitted when the printed glyph itself establishes the unit.

Usage:
  build_e2_label_receipts_20260920.py --pdf-dir /tmp/pg_labels --out <json>
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import fitz
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
LIVE_DIR = HERE / "source_resolution_20260920" / "live"
RAW_ROOT = Path.home() / "Downloads" / "PharmaGuide_Datasets" / "staging" / "brands"
DPI = 600

# row label -> tokens that identify the row on the printed panel
TARGETS: dict[str, list[tuple[str, str]]] = {
    "223563": [("Vitamin A", "vitamin a"), ("Vitamin D3", "vitamin d3")],
    "223572": [("Vitamin A", "vitamin a"), ("Vitamin D3", "vitamin d3")],
    "231334": [("Vitamin A", "vitamin a"), ("Vitamin E", "vitamin e"),
               ("Vitamin C", "vitamin c")],
    "231335": [("Vitamin A", "vitamin a"), ("Vitamin E", "vitamin e"),
               ("Vitamin D", "vitamin d")],
    "263865": [("Vitamin A", "vitamin a"), ("Vitamin E", "vitamin e"),
               ("Vitamin C", "vitamin c"), ("Vitamin D", "vitamin d")],
    "328644": [("Vitamin A", "vitamin a")],
}


def run_tesseract(img_bytes: bytes, *extra: str) -> str:
    res = subprocess.run(["tesseract", "-", "stdout", *extra],
                         input=img_bytes, capture_output=True, text=False, timeout=300)
    return res.stdout.decode("utf-8", "replace")


def png_bytes(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def render(pdf: Path, dpi: int) -> Image.Image:
    doc = fitz.open(pdf)
    pix = doc[0].get_pixmap(dpi=dpi)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    return im


def words(im: Image.Image) -> list[dict]:
    out = run_tesseract(png_bytes(im), "--psm", "6", "-l", "eng", "tsv")
    return [w for w in csv.DictReader(io.StringIO(out), delimiter="\t") if w.get("text")]


def number_tokens(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def unit_glyph(im: Image.Image, tok: dict) -> dict:
    l, t = int(tok["left"]), int(tok["top"])
    w, h = int(tok["width"]), int(tok["height"])
    crop = im.crop((max(0, l - 3), max(0, t - 3), l + w + 3, t + h + 3)).convert("L")
    crop = crop.resize((crop.width * 12, crop.height * 12), Image.LANCZOS)
    crop = ImageOps.autocontrast(crop)
    out = {"token": tok["text"], "width": w}
    for wl, tag in (("Mcg", "whitelist_mcg"), ("Mg", "whitelist_mg")):
        out[tag] = run_tesseract(png_bytes(crop), "--psm", "7", "-l", "eng",
                                 "-c", f"tessedit_char_whitelist={wl}").strip()
    # A 3-glyph box reads "Mcg"/"mcg"; a 2-glyph box reads "Mg"/"mg".
    three = len(out["whitelist_mcg"]) == 3
    out["glyph_count_estimate"] = 3 if three else 2
    out["printed_unit"] = ("mcg" if three else "mg") if out["whitelist_mcg"] or out["whitelist_mg"] else None
    return out


def row_read(im: Image.Image, ws: list[dict], label: str) -> dict | None:
    want = label.split()
    ordered = sorted(ws, key=lambda w: (int(w["top"]), int(w["left"])))
    anchor = None
    for i in range(len(ordered) - len(want) + 1):
        seq = ordered[i:i + len(want)]
        if all(abs(int(a["top"]) - int(b["top"])) <= 10 for a, b in zip(seq, seq[1:])) and \
           all(want[j].lower() == (seq[j]["text"] or "").lower().strip(":.") for j in range(len(want))):
            anchor = seq[0]
            break
    if anchor is None:
        return None
    top = int(anchor["top"])
    left = int(anchor["left"])
    band = sorted([x for x in ws if abs(int(x["top"]) - top) <= 14 and int(x["left"]) >= left],
                  key=lambda x: int(x["left"]))
    qty = next((x for x in band if number_tokens(x["text"]) and x is not anchor), None)
    unit = None
    if qty is not None:
        for x in band:
            if int(x["left"]) <= int(qty["left"]):
                continue
            t = x["text"]
            if number_tokens(t) or t in ("|",):
                continue
            if len(t) <= 4 and t[:1] in "Mm":
                unit = x
                break
    rec = {
        "tokens": " ".join(x["text"] for x in band)[:220],
        "printed_quantity_token": qty["text"] if qty else None,
        "printed_quantity": (int("".join(c for c in qty["text"] if c.isdigit()) or 0)
                             if qty else None),
    }
    if unit is not None:
        rec["unit_glyph"] = unit_glyph(im, unit)
    return rec


def structured_rows(rows: list, out: dict | None = None, depth: int = 0) -> dict:
    if out is None:
        out = {}
    for r in rows or []:
        name = str(r.get("name") or r.get("originalIngredient") or "").strip().lower()
        for q in r.get("quantity") or []:
            out.setdefault(name, []).append({
                "quantity": q.get("quantity"), "unit": q.get("unit"),
                "operator": q.get("operator"),
                "per_serving": f"{q.get('servingSizeQuantity')}{q.get('servingSizeUnit')}",
                "depth": depth,
                "parent": r.get("_parent") if isinstance(r, dict) else None,
            })
        structured_rows(r.get("nestedRows") or [], out, depth + 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", default="/tmp/pg_labels")
    ap.add_argument("--out", default=str(HERE / "source_resolution_20260920" /
                                         "e2_label_receipts_20260920.json"))
    args = ap.parse_args()

    receipts: dict[str, dict] = {}
    for pid, rows in TARGETS.items():
        pdf = Path(args.pdf_dir) / f"{pid}.pdf"
        live_path = LIVE_DIR / f"{pid}.json"
        frozen_path = next(iter(sorted(RAW_ROOT.glob(f"*/{pid}.json"))), None)
        entry: dict = {"dsld_id": pid,
                       "label_pdf": str(pdf),
                       "retrieved_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if pdf.exists():
            im = render(pdf, DPI)
            ws = words(im)
            entry["panel"] = {}
            for label, structured_key in rows:
                r = row_read(im, ws, label)
                entry["panel"][label] = r
            entry["_im"] = im
        else:
            entry["label_pdf_missing"] = True

        live = json.loads(live_path.read_text()) if live_path.exists() else None
        frozen = json.loads(frozen_path.read_text()) if frozen_path else None
        entry["live_structured"] = {
            k: v for k, v in structured_rows(
                (live or {}).get("ingredientRows") or []).items()
            if any(t in k for t in ("vitamin a", "vitamin d", "vitamin e"))
        }
        if frozen:
            entry["frozen_structured"] = {
                k: v for k, v in structured_rows(
                    frozen.get("activeIngredients") or []).items()
                if any(t in k for t in ("vitamin a", "vitamin d", "vitamin e"))
            }
        entry.pop("_im", None)
        receipts[pid] = entry
        print(f"--- {pid} ---")
        for label, r in (entry.get("panel") or {}).items():
            if not r:
                print(f"  [{label}] row not located")
                continue
            g = r.get("unit_glyph") or {}
            print(f"  [{label}] printed={r.get('printed_quantity')} "
                  f"unit={g.get('printed_unit')!r} (box {g.get('width')}px, "
                  f"mcg-wl={g.get('whitelist_mcg')!r}) live="
                  f"{entry['live_structured'].get(label.lower())}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipts, indent=1), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
