#!/usr/bin/env python3
"""Prove every Phase-3 source correction reached the product lane.

Team instruction #14: for each `source_verified_correction` show
`receipt -> correction layer -> normalized row`, not merely that a receipt
exists. For each `intentional_non_scoreable`/withheld item show its explicit
machine reason.

Read-only. Loads the frozen raw DSLD record for each target, runs the real
cleaner (`EnhancedDSLDNormalizer.normalize_product`), and dumps the target rows
before and after so the review can see the correction applied in the lane.

Usage:
    "$PG_PYTHON" prove_source_corrections_20260920.py [--out PATH]
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402

CORPUS = Path(
    os.environ.get("PG_BRAND_CORPUS")
    or os.path.expanduser("~/Downloads/PharmaGuide_Datasets/staging/brands")
)

# (dsld_id, [row names whose cleaned form is the evidence for this product])
TARGETS = [
    ("223563", ["Vitamin A"]),
    ("223572", ["Vitamin A"]),
    ("328644", ["Vitamin A"]),
    ("231334", ["Vitamin A"]),   # withheld — must be untouched
    ("231335", ["Vitamin A"]),   # withheld — must be untouched
    ("263865", ["Vitamin A"]),   # withheld — must be untouched
    ("228823", ["Vitamin A"]),
    ("243799", ["Vitamin A"]),
    ("243808", ["Vitamin A", "Folate"]),
    ("243812", ["Vitamin A"]),
    ("243815", ["Vitamin A"]),
    ("201420", ["Folate", "Folic Acid"]),
    ("246430", ["Folate"]),
    ("269360", ["Serrapeptase Enzyme"]),
    # dispositions
    ("12300", ["Proprietary Blend", "Total Carbohydrates"]),
    ("254396", ["Vitamin B12"]),
    ("254413", ["Vitamin B12"]),
    ("75291", ["Total Omega-3 Fatty Acids", "Omega-3"]),
]


def load_raw(dsld_id: str) -> dict | None:
    for path in CORPUS.glob(f"*/{dsld_id}.json"):
        return json.loads(path.read_text())
    return None


def find_rows(rows, wanted, out, depth=0):
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        if any(w.lower() in name.lower() for w in wanted):
            out.append(
                {
                    "depth": depth,
                    "name": row.get("name"),
                    "quantity": row.get("quantity"),
                    "unit": row.get("unit"),
                    "forms": [
                        form.get("name")
                        for form in (row.get("forms") or [])
                        if isinstance(form, dict)
                    ],
                }
            )
        find_rows(
            row.get("ingredients") or row.get("nestedRows"), wanted, out, depth + 1
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(
            Path(__file__).resolve().parent
            / "source_resolution_20260920"
            / "LANE_PROOF_20260920.json"
        ),
    )
    args = parser.parse_args()

    normalizer = EnhancedDSLDNormalizer()
    report = {
        "artifact": "Phase-3 source-correction lane proof",
        "generated_by": "prove_source_corrections_20260920.py",
        "what_this_shows": (
            "receipt -> correction layer -> cleaned lane row. Raw = the frozen "
            "source row; cleaned = the row the normalizer produced after "
            "RC-5/disposition application."
        ),
        "products": {},
    }

    for dsld_id, wanted in TARGETS:
        raw = load_raw(dsld_id)
        if raw is None:
            report["products"][dsld_id] = {"error": "not found in corpus"}
            continue
        # The correction layer mutates rows in place, so every snapshot must be
        # taken from its own deep copy or the "before" view would silently show
        # the corrected values (and the evidence would be a lie).
        pre = []
        find_rows(copy.deepcopy(raw.get("ingredientRows")), wanted, pre)
        corrected_rows = normalizer._apply_label_corrections(
            copy.deepcopy(raw.get("ingredientRows")), dsld_id
        )
        applied = []
        find_rows(corrected_rows, wanted, applied)
        cleaned = normalizer.normalize_product(copy.deepcopy(raw))
        rows = cleaned.get("ingredients") or cleaned.get("activeIngredients") or []
        post = []
        for row in rows:
            name = str(row.get("name") or "")
            if any(w.lower() in name.lower() for w in wanted):
                post.append(
                    {
                        "name": row.get("name"),
                        "quantity": row.get("quantity"),
                        "unit": row.get("unit"),
                        "cleaner_row_role": row.get("cleaner_row_role"),
                        "score_eligible_by_cleaner": row.get("score_eligible_by_cleaner"),
                        "score_exclusion_reason": row.get("score_exclusion_reason"),
                        "canonical_id": row.get("canonical_id"),
                        "forms": [
                            form.get("name")
                            for form in (row.get("forms") or [])
                            if isinstance(form, dict)
                        ],
                        "pre_correction_name": row.get("_pre_correction_name"),
                        "pre_correction_quantity_unit": row.get(
                            "_pre_correction_quantity_unit"
                        ),
                        "pre_correction_quantity_value": row.get(
                            "_pre_correction_quantity_value"
                        ),
                        "pre_correction_forms": row.get("_pre_correction_forms"),
                    }
                )
        report["products"][dsld_id] = {
            "brand": raw.get("brandName"),
            "product": raw.get("fullName"),
            "raw_rows": pre,
            "after_correction_layer_rows": applied,
            "cleaned_rows": post,
        }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1), encoding="utf-8")

    for dsld_id, entry in report["products"].items():
        print(f"=== {dsld_id} {entry.get('product')} ===")
        for row in entry.get("raw_rows", []):
            print(f"  raw     : {row['name']!r} qty={row['quantity']} unit={row['unit']!r}")
        for row in entry.get("after_correction_layer_rows", []):
            print(f"  rc5     : {row['name']!r} qty={row['quantity']} unit={row['unit']!r} forms={row['forms']}")
        for row in entry.get("cleaned_rows", []):
            marks = [
                f"{key}={row[key]!r}"
                for key in (
                    "pre_correction_name",
                    "pre_correction_quantity_unit",
                    "pre_correction_quantity_value",
                    "pre_correction_forms",
                )
                if row.get(key) not in (None, [])
            ]
            print(
                f"  cleaned : {row['name']!r} qty={row['quantity']} unit={row['unit']!r} "
                f"role={row['cleaner_row_role']} eligible={row['score_eligible_by_cleaner']} "
                f"forms={row['forms']} corrected={marks}"
            )
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
