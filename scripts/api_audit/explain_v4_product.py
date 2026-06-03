#!/usr/bin/env python3
"""Explain one v4 product from its enriched blob.

Prints the ScoringClassification v1 route contract plus the v4 scoring trace so
route/profile bugs can be debugged from a persisted product id.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (str(SCRIPTS_ROOT), str(SCRIPTS_ROOT / "api_audit")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scoring_input_contract import build_scoring_classification, get_scoring_ingredients  # noqa: E402
from score_supplements_v4_shadow import score_product_v4_shadow  # noqa: E402
import v4_shadow_canary_report as canary  # noqa: E402


DEFAULT_PRODUCTS_ROOT = SCRIPTS_ROOT / "products"


def _load_product(dsld_id: str, products_root: Path) -> Dict[str, Any]:
    index = canary.build_enriched_index(products_root)
    product = index.get(str(dsld_id))
    if not product:
        raise SystemExit(f"ERROR: dsld_id {dsld_id} not found under {products_root}")
    return product


def explain_product(product: Dict[str, Any]) -> Dict[str, Any]:
    classification = build_scoring_classification(product)
    scoring_input = get_scoring_ingredients(product, strict=True)
    shadow = score_product_v4_shadow(product)
    breakdown = shadow.get("shadow_score_v4_breakdown") if isinstance(shadow, dict) else {}
    module = breakdown.get("module") if isinstance(breakdown, dict) else {}
    completeness = breakdown.get("completeness_gate") if isinstance(breakdown, dict) else {}
    safety = breakdown.get("safety_gate") if isinstance(breakdown, dict) else {}
    return {
        "dsld_id": canary._dsld_id(product),
        "brand_name": product.get("brand_name"),
        "product_name": product.get("product_name") or product.get("fullName"),
        "primary_type": product.get("primary_type") or canary._safe_dict(product.get("supplement_taxonomy")).get("primary_type"),
        "classification": classification,
        "scoring_input": scoring_input.diagnostics(),
        "v4": {
            "score": shadow.get("shadow_score_v4_100"),
            "verdict": shadow.get("shadow_score_v4_verdict"),
            "module": shadow.get("shadow_score_v4_module"),
            "confidence": shadow.get("shadow_score_v4_confidence"),
            "completeness_gate": completeness,
            "safety_gate": safety,
            "module_trace": module,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dsld_id", help="DSLD product id to explain")
    parser.add_argument("--products-root", type=Path, default=DEFAULT_PRODUCTS_ROOT)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    product = _load_product(args.dsld_id, args.products_root)
    report = explain_product(product)
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
