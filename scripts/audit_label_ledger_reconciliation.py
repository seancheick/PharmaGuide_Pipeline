#!/usr/bin/env python3
"""Deterministic label-ledger reconciliation audit over the real DSLD corpus.

Reproduces the enrichment-contract validation the pipeline gate runs, over a
FIXED, seeded sample of real brand source files, so a reconciliation claim is
reproducible instead of ad-hoc. Requires the local DSLD staging data (raw
label JSON is not committed to the repo).

Usage (from scripts/):
    python3 audit_label_ledger_reconciliation.py                # cleaner-side, default brands
    python3 audit_label_ledger_reconciliation.py --enrich       # full clean+enrich (real gate input)
    python3 audit_label_ledger_reconciliation.py --brands Solgar CVS --per-brand 60
    python3 audit_label_ledger_reconciliation.py --report /tmp/audit.json

Determinism: files are sorted and sampled with a fixed --seed, so the same
arguments always select the same products.
"""

import argparse
import glob
import json
import logging
import os
import random
import sys
from collections import Counter

# The 20 brands the 2026-07-20 full-corpus run failed at the enrichment gate.
DEFAULT_BRANDS = [
    "BulkSupplements", "CVS", "Doctors_Best", "Double_Wood_Supplements", "Equate",
    "GNC", "Garden_of_life", "Jarrow_Formulas", "Life_Extension", "Nature_Made",
    "Natures_Bounty", "Natures_Way", "Nutricost", "Pure_Encapsulations", "Solgar",
    "Sports_Research", "Spring_Valley", "Thorne", "Vitafusion", "nordic-naturals",
]
DEFAULT_STAGING = "/Users/seancheick/Documents/DataSetDsld/staging/brands"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--staging", default=DEFAULT_STAGING)
    ap.add_argument("--brands", nargs="*", default=DEFAULT_BRANDS)
    ap.add_argument("--per-brand", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--enrich", action="store_true",
                    help="run full clean+enrich (matches the real gate input)")
    ap.add_argument("--report", default=None, help="write JSON summary to this path")
    args = ap.parse_args()

    logging.disable(logging.CRITICAL)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrichment_contract_validator import EnrichmentContractValidator

    norm = EnhancedDSLDNormalizer()
    validator = EnrichmentContractValidator(strict_mode=True)
    enricher = None
    if args.enrich:
        from enrich_supplements_v3 import SupplementEnricherV3
        enricher = SupplementEnricherV3()

    rng = random.Random(args.seed)
    total = 0
    total_errors = 0
    input_errors = 0
    by_brand: dict = {}
    by_rule: Counter = Counter()

    for brand in args.brands:
        files = sorted(glob.glob(os.path.join(args.staging, brand, "*.json")))
        if not files:
            input_errors += 1
            by_brand[brand] = {
                "sampled": 0,
                "products": 0,
                "unreadable_files": 0,
                "errors": 0,
                "status": "missing",
                "note": "no raw files",
            }
            continue
        sample = rng.sample(files, min(args.per_brand, len(files)))
        brand_errors = 0
        brand_products = 0
        unreadable_files = 0
        for path in sample:
            try:
                with open(path, encoding="utf-8") as handle:
                    raw = json.load(handle)
            except (OSError, json.JSONDecodeError):
                unreadable_files += 1
                input_errors += 1
                continue
            product = norm.normalize_product(raw)
            if enricher is not None:
                product, _ = enricher.enrich_product(product)
            errs = [v for v in validator.validate(product) if v.severity == "error"]
            total += 1
            brand_products += 1
            total_errors += len(errs)
            brand_errors += len(errs)
            for v in errs:
                by_rule[getattr(v, "rule", "?")] += 1
        by_brand[brand] = {
            "sampled": len(sample),
            "products": brand_products,
            "unreadable_files": unreadable_files,
            "errors": brand_errors,
            "status": "ok" if unreadable_files == 0 else "input_error",
        }

    result = {
        "mode": "clean+enrich" if args.enrich else "clean",
        "seed": args.seed,
        "per_brand": args.per_brand,
        "products_checked": total,
        "contract_errors": total_errors,
        "input_errors": input_errors,
        "errors_by_rule": dict(by_rule.most_common()),
        "by_brand": by_brand,
    }
    print(json.dumps(result, indent=2))
    if args.report:
        with open(args.report, "w") as fh:
            json.dump(result, fh, indent=2)
        print(f"\nreport written: {args.report}")
    is_clean = total_errors == 0 and input_errors == 0
    print(
        f"\n{total} products, {total_errors} contract errors, "
        f"{input_errors} input errors ({'CLEAN' if is_clean else 'FAILURES'})"
    )
    return 0 if is_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
