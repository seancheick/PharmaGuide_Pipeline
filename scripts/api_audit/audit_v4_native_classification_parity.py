#!/usr/bin/env python3
"""Audit persisted native ScoringClassification v1 parity.

Fresh enrichment artifacts should persist ``product_scoring_classification``.
This audit compares that embedded native contract against the same shared
builder run over the product blob. Compatibility-era artifacts may omit the
field; pass ``--require-native`` for release/P5 gates once a fresh enrich has
been generated.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (str(SCRIPTS_ROOT), str(SCRIPTS_ROOT / "api_audit")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scoring_input_contract import build_scoring_classification  # noqa: E402
import v4_shadow_canary_report as canary  # noqa: E402


DEFAULT_PRODUCTS_ROOT = SCRIPTS_ROOT / "products"
DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "v4_native_classification_parity"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_enriched_products(products_root: Path) -> List[Dict[str, Any]]:
    """Load enriched batch products from either operational or temp roots.

    The canary report loader only indexes the operational
    ``output_*_enriched/enriched`` layout. Native parity is also run against
    sample enrich outputs such as ``/tmp/.../enriched`` before a full rebuild,
    so this audit owns a broader loader and must not silently pass on zero rows.
    """
    products: List[Dict[str, Any]] = []
    seen_paths = sorted({
        path
        for path in products_root.rglob("enriched_cleaned_batch_*.json")
        if path.is_file()
    })
    for path in seen_paths:
        products.extend(canary._iter_products(path))
    return products


def audit_products(products: Iterable[Dict[str, Any]], *, require_native: bool = False) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    total = 0
    native_count = 0
    missing_count = 0
    malformed_count = 0
    mismatch_count = 0

    for product in products:
        if not isinstance(product, dict):
            continue
        total += 1
        dsld_id = canary._dsld_id(product)
        embedded = product.get("product_scoring_classification")
        if embedded is None:
            missing_count += 1
            if require_native:
                rows.append({
                    "dsld_id": dsld_id,
                    "brand_name": product.get("brand_name"),
                    "product_name": product.get("product_name") or product.get("fullName"),
                    "issue": "missing_native_classification",
                    "embedded_route": None,
                    "derived_route": None,
                    "embedded_origin": None,
                    "derived_origin": None,
                })
            continue
        if not isinstance(embedded, dict):
            malformed_count += 1
            rows.append({
                "dsld_id": dsld_id,
                "brand_name": product.get("brand_name"),
                "product_name": product.get("product_name") or product.get("fullName"),
                "issue": "malformed_native_classification",
                "embedded_route": None,
                "derived_route": None,
                "embedded_origin": None,
                "derived_origin": None,
            })
            continue

        native_count += 1
        derived = build_scoring_classification(product, classification_origin="native_enrichment")
        if _canonical_json(embedded) != _canonical_json(derived):
            mismatch_count += 1
            rows.append({
                "dsld_id": dsld_id,
                "brand_name": product.get("brand_name"),
                "product_name": product.get("product_name") or product.get("fullName"),
                "issue": "native_builder_mismatch",
                "embedded_route": embedded.get("route_module"),
                "derived_route": derived.get("route_module"),
                "embedded_origin": embedded.get("classification_origin"),
                "derived_origin": derived.get("classification_origin"),
            })

    if total == 0:
        rows.append({
            "dsld_id": None,
            "brand_name": None,
            "product_name": None,
            "issue": "no_products_loaded",
            "embedded_route": None,
            "derived_route": None,
            "embedded_origin": None,
            "derived_origin": None,
        })

    blocked_count = len(rows)
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_products": total,
        "native_classification_count": native_count,
        "missing_native_classification_count": missing_count,
        "malformed_native_classification_count": malformed_count,
        "native_builder_mismatch_count": mismatch_count,
        "require_native": require_native,
        "blocking_issue_count": blocked_count,
        "ready": blocked_count == 0,
        "issues": rows,
    }


def _write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    fields = [
        "dsld_id",
        "brand_name",
        "product_name",
        "issue",
        "embedded_route",
        "derived_route",
        "embedded_origin",
        "derived_origin",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-root", type=Path, default=DEFAULT_PRODUCTS_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--require-native", action="store_true")
    args = parser.parse_args()

    products = load_enriched_products(args.products_root)
    summary = audit_products(products, require_native=args.require_native)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(
        json.dumps({k: v for k, v in summary.items() if k != "issues"}, indent=2) + "\n"
    )
    _write_csv(summary["issues"], args.out_dir / "issues.csv")
    print(json.dumps({k: v for k, v in summary.items() if k != "issues"}, indent=2))
    return 0 if summary["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
