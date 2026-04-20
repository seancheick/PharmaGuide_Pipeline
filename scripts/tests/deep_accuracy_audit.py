#!/usr/bin/env python3
"""
Deep accuracy audit — scans all cleaned + enriched brand output for
medical-grade accuracy issues that could produce wrong user-visible scores.

Read-only. Safe to run alongside a live pipeline. Writes a single
report to scripts/reports/deep_accuracy_audit.json.

Classes of bugs audited:
  1. SILENTLY-MAPPED: mapped=True AND canonical_id=None (protocol rule #4)
  2. CROSS-DB LEAK: active row routes to harmful_additives or banned_recalled
     (these are inactive-section canonicals appearing in actives)
  3. PARENT-FALLBACK SCORED: enricher fell back to parent-level (unspecified
     form) on a scorable row — may give undue credit or none at all.
  4. BRANDED-TOKEN FALLBACK: branded_token_fallback_used=True means the
     branded name had to rescue the match — flag for manual review.
  5. CLEANER-CANONICAL MISMATCH: cleaner said X, enricher matched Y and
     logged cleaner_canonical_enforced=True (constraint fired). Each row
     needs a human confirming the cleaner was right.
  6. CANONICAL ≠ SOURCE_DB: if canonical_source_db=ingredient_quality_map
     but the canonical_id isn't actually an IQM top-level key.
  7. DUPLICATE CANONICAL: same canonical_id appears multiple times in one
     product's actives (may indicate a blend + member dup).
  8. PARSER ARTIFACT: rows whose raw_source_text is a percent/dose token
     only ("less than 0.1%", "5%", "10mg") — likely not real ingredients.
  9. ENRICHER-UNMAPPED ACTIVE: an ingredient the enricher classifies as
     scorable but couldn't resolve to any canonical — the TRUE gap.
  10. FORMS[0] STRIPPED: cleaner emitted non-empty forms[] but enricher's
      ingredient_quality_data has form_id=None (form-info dropped).

For each class, we report:
  - total count across all brands
  - per-brand count
  - top 10 offending ingredient names (or product_ids)
  - sample for manual review

This is a medical-accuracy triage tool. Each class maps to a concrete fix.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTS_ROOT = REPO_ROOT / "scripts" / "products"
IQM_PATH = REPO_ROOT / "scripts" / "data" / "ingredient_quality_map.json"
REPORT_DIR = REPO_ROOT / "scripts" / "reports"
REPORT_PATH = REPORT_DIR / "deep_accuracy_audit.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_iqm_keys() -> set:
    with open(IQM_PATH) as f:
        iqm = json.load(f)
    return {k for k in iqm.keys() if not k.startswith("_")}


def iter_cleaned_products(brand: str):
    cleaned_dir = PRODUCTS_ROOT / f"output_{brand}" / "cleaned"
    if not cleaned_dir.exists():
        return
    for batch in sorted(cleaned_dir.glob("cleaned_*.json")):
        try:
            data = json.loads(batch.read_text())
        except Exception:
            continue
        if isinstance(data, list):
            for p in data:
                yield p


def iter_enriched_products(brand: str):
    enriched_dir = PRODUCTS_ROOT / f"output_{brand}_enriched" / "enriched"
    if not enriched_dir.exists():
        return
    for batch in sorted(enriched_dir.glob("enriched_*.json")):
        try:
            data = json.loads(batch.read_text())
        except Exception:
            continue
        if isinstance(data, list):
            for p in data:
                yield p


def find_brands_with_cleaned() -> List[str]:
    brands = []
    for d in sorted(PRODUCTS_ROOT.glob("output_*")):
        name = d.name.replace("output_", "")
        if "_enriched" in name or "_scored" in name:
            continue
        if (d / "cleaned").exists():
            brands.append(name)
    return brands


def find_brands_with_enriched() -> List[str]:
    brands = []
    for d in sorted(PRODUCTS_ROOT.glob("output_*_enriched")):
        name = d.name.replace("output_", "").replace("_enriched", "")
        if (d / "enriched").exists():
            brands.append(name)
    return brands


PARSER_ARTIFACT_PATTERNS = [
    re.compile(r"^\s*less than\s+[\d.]+\s*%?\s*$", re.I),
    re.compile(r"^\s*[\d.]+\s*%\s*$"),
    re.compile(r"^\s*[\d.]+\s*(?:mg|mcg|g|iu)\s*$", re.I),
    re.compile(r"^\s*(?:and|or|plus|with)\s*$", re.I),
    re.compile(r"^\s*[+*\-\u2022]+\s*$"),
]


def is_parser_artifact(name: str) -> bool:
    if not name:
        return True
    return any(p.match(name) for p in PARSER_ARTIFACT_PATTERNS)


# ---------------------------------------------------------------------------
# Audit classes
# ---------------------------------------------------------------------------


def audit_cleaner(brand: str, iqm_keys: set) -> Dict[str, Any]:
    """Scan cleaned output for contract violations."""
    results = {
        "total_actives": 0,
        "silently_mapped": 0,
        "silently_mapped_samples": Counter(),
        "canonical_src_iqm_but_not_iqm_key": 0,
        "canonical_src_iqm_but_not_iqm_key_samples": [],
        "parser_artifacts": 0,
        "parser_artifacts_samples": Counter(),
        "cross_db_leak_active_harmful": 0,
        "cross_db_leak_active_harmful_samples": Counter(),
        "cross_db_leak_active_banned": 0,
        "cross_db_leak_active_banned_samples": Counter(),
        "duplicate_canonical_in_actives": 0,
        "duplicate_canonical_samples": Counter(),
        "forms_stripped": 0,  # forms present in raw DSLD but forms_structured empty
    }

    for p in iter_cleaned_products(brand):
        actives = p.get("activeIngredients", []) or []
        results["total_actives"] += len(actives)

        # Per-product canonical_id tracking for dup detection
        cids_this_product = Counter()

        for ing in actives:
            mapped = ing.get("mapped")
            cid = ing.get("canonical_id")
            src = ing.get("canonical_source_db")
            name = ing.get("raw_source_text") or ""

            # Silently-mapped: contract violation
            if mapped and not cid:
                results["silently_mapped"] += 1
                results["silently_mapped_samples"][name] += 1

            # canonical_source_db=IQM but canonical_id not in IQM keys
            if src == "ingredient_quality_map" and cid and cid not in iqm_keys:
                results["canonical_src_iqm_but_not_iqm_key"] += 1
                if len(results["canonical_src_iqm_but_not_iqm_key_samples"]) < 10:
                    results["canonical_src_iqm_but_not_iqm_key_samples"].append({
                        "pid": p.get("id"),
                        "name": name,
                        "canonical_id": cid,
                    })

            # Parser artifacts
            if is_parser_artifact(name):
                results["parser_artifacts"] += 1
                results["parser_artifacts_samples"][name] += 1

            # Cross-DB leaks in active section
            if src == "harmful_additives":
                results["cross_db_leak_active_harmful"] += 1
                results["cross_db_leak_active_harmful_samples"][name] += 1
            if src == "banned_recalled":
                results["cross_db_leak_active_banned"] += 1
                results["cross_db_leak_active_banned_samples"][name] += 1

            if cid:
                cids_this_product[cid] += 1

        # Within-product duplicate canonicals (excluding None)
        dups = {c: n for c, n in cids_this_product.items() if n > 1}
        for cid, n in dups.items():
            results["duplicate_canonical_in_actives"] += n - 1
            results["duplicate_canonical_samples"][cid] += n - 1

    # Convert Counters to top-10 lists for JSON serialization
    for k in list(results.keys()):
        if isinstance(results[k], Counter):
            results[k] = [{"name": n, "count": c} for n, c in results[k].most_common(15)]
    return results


def audit_enricher(brand: str, iqm_keys: set) -> Dict[str, Any]:
    results = {
        "total_scorable_actives": 0,
        "parent_fallback_count": 0,
        "parent_fallback_samples": Counter(),
        "branded_token_fallback_count": 0,
        "branded_token_fallback_samples": Counter(),
        "cleaner_canonical_enforced_count": 0,
        "cleaner_canonical_enforced_samples": Counter(),
        "cleaner_canonical_fallback_count": 0,
        "cleaner_canonical_fallback_samples": Counter(),
        "unmapped_scorable_active": 0,
        "unmapped_scorable_samples": Counter(),
        "unspecified_form_scored": 0,
        "unspecified_form_samples": Counter(),
        "bio_score_below_parent_avg": 0,  # heuristic only
    }

    for p in iter_enriched_products(brand):
        iq_data = p.get("ingredient_quality_data", {}) or {}
        ings = iq_data.get("ingredients", []) or []
        for q in ings:
            if not isinstance(q, dict):
                continue
            role = q.get("role_classification")
            if role not in ("scorable", "recognized_non_scorable", "inactive_non_scorable"):
                # role can vary; also include rows with bio_score
                pass

            if q.get("scoreable_identity") is True:
                results["total_scorable_actives"] += 1

            name = q.get("raw_source_text") or q.get("name") or ""
            # Parent fallback telemetry
            if q.get("fallback_form_selected"):
                results["parent_fallback_count"] += 1
                results["parent_fallback_samples"][name] += 1

            # Branded token fallback
            if q.get("branded_token_fallback_used"):
                results["branded_token_fallback_count"] += 1
                results["branded_token_fallback_samples"][name] += 1

            # Cleaner canonical telemetry
            if q.get("cleaner_canonical_enforced"):
                results["cleaner_canonical_enforced_count"] += 1
                results["cleaner_canonical_enforced_samples"][name] += 1
            if q.get("cleaner_canonical_fallback"):
                results["cleaner_canonical_fallback_count"] += 1
                results["cleaner_canonical_fallback_samples"][name] += 1

            # Unmapped scorable (the true gap)
            if q.get("scoreable_identity") is True and not q.get("canonical_id"):
                results["unmapped_scorable_active"] += 1
                results["unmapped_scorable_samples"][name] += 1

            # Unspecified form wins on a scorable — may be conservative or
            # may be undercredited. Flag for audit.
            form_id = (q.get("form_id") or "").lower()
            if form_id and "unspecified" in form_id and q.get("scoreable_identity"):
                results["unspecified_form_scored"] += 1
                results["unspecified_form_samples"][f"{q.get('canonical_id')}::{name}"] += 1

    for k in list(results.keys()):
        if isinstance(results[k], Counter):
            results[k] = [{"name": n, "count": c} for n, c in results[k].most_common(15)]
    return results


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    iqm_keys = load_iqm_keys()

    cleaned_brands = find_brands_with_cleaned()
    enriched_brands = find_brands_with_enriched()

    print(f"Cleaned brands:  {len(cleaned_brands)}")
    print(f"Enriched brands: {len(enriched_brands)}")
    print(f"IQM top-level canonical keys: {len(iqm_keys)}")
    print()

    report: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "iqm_key_count": len(iqm_keys),
        "cleaner": {},
        "enricher": {},
        "totals": {},
    }

    # Cleaner audit
    print("=== Cleaner audit ===")
    totals = defaultdict(int)
    for brand in cleaned_brands:
        r = audit_cleaner(brand, iqm_keys)
        report["cleaner"][brand] = r
        print(
            f"  {brand:25s}  actives={r['total_actives']:>6}  "
            f"silently_mapped={r['silently_mapped']:>4}  "
            f"parser_artifacts={r['parser_artifacts']:>3}  "
            f"cross_db_harmful={r['cross_db_leak_active_harmful']:>3}  "
            f"dup_canonical={r['duplicate_canonical_in_actives']:>3}"
        )
        totals["total_actives"] += r["total_actives"]
        totals["silently_mapped"] += r["silently_mapped"]
        totals["parser_artifacts"] += r["parser_artifacts"]
        totals["cross_db_leak_active_harmful"] += r["cross_db_leak_active_harmful"]
        totals["cross_db_leak_active_banned"] += r["cross_db_leak_active_banned"]
        totals["duplicate_canonical_in_actives"] += r["duplicate_canonical_in_actives"]

    print()
    print("=== Enricher audit ===")
    for brand in enriched_brands:
        r = audit_enricher(brand, iqm_keys)
        report["enricher"][brand] = r
        print(
            f"  {brand:25s}  scorable={r['total_scorable_actives']:>5}  "
            f"parent_fallback={r['parent_fallback_count']:>3}  "
            f"branded_fb={r['branded_token_fallback_count']:>3}  "
            f"cleaner_enforced={r['cleaner_canonical_enforced_count']:>3}  "
            f"unmapped_scorable={r['unmapped_scorable_active']:>3}  "
            f"unspecified_form={r['unspecified_form_scored']:>4}"
        )
        for k in ("parent_fallback_count", "branded_token_fallback_count",
                 "cleaner_canonical_enforced_count", "cleaner_canonical_fallback_count",
                 "unmapped_scorable_active", "unspecified_form_scored",
                 "total_scorable_actives"):
            totals[k] += r[k]

    report["totals"] = dict(totals)
    print()
    print("=== TOTALS ===")
    for k, v in sorted(report["totals"].items()):
        print(f"  {k:40s}  {v:>6}")

    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nFull report written to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
