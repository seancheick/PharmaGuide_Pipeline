#!/usr/bin/env python3
"""Audit v4 dose dimensions that score zero.

This is intentionally an audit, not a score floor. Evidence of a disclosed dose
should either be credited by the route-specific dose scorer or classified as a
valid zero (trace, unsafe, or undisclosed). Anything else is a review candidate.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules.generic_helpers import (  # noqa: E402
    get_active_ingredients,
    has_usable_individual_dose,
    _as_float,
    _norm_text,
    _safe_list,
)
from scoring_v4.router import class_for_product  # noqa: E402


OMEGA_TRACE_THRESHOLD_MG_DAY = 100.0


def _score_dose_for_route(product: Dict[str, Any], route: str) -> Dict[str, Any]:
    if route == "omega":
        from scoring_v4.modules.omega_dose import score_dose
    elif route == "probiotic":
        from scoring_v4.modules.probiotic_dose import score_dose
    elif route == "multi_or_prenatal":
        from scoring_v4.modules.multi_prenatal_dose import score_dose
    elif route == "sports":
        from scoring_v4.modules.sports_dose import score_dose
    else:
        from scoring_v4.modules.generic_dose import score_dose
    return score_dose(product)


def _has_unsafe_overdose(product: Dict[str, Any]) -> bool:
    rda_ul = product.get("rda_ul_data")
    flags = _safe_list(rda_ul.get("safety_flags") if isinstance(rda_ul, dict) else None)
    for flag in flags:
        if isinstance(flag, dict) and (_as_float(flag.get("pct_ul"), 0.0) or 0.0) >= 150.0:
            return True
    return False


def _has_meaningful_disclosed_dose(product: Dict[str, Any]) -> bool:
    for row in get_active_ingredients(product):
        if not isinstance(row, dict):
            continue
        if row.get("is_parent_total"):
            continue
        if has_usable_individual_dose(row):
            return True

    for evidence in _safe_list(product.get("product_scoring_evidence")):
        if not isinstance(evidence, dict):
            continue
        if evidence.get("scoreable") is False:
            continue
        dose_value = _as_float(evidence.get("dose_value"), None)
        if dose_value is None or dose_value <= 0:
            continue
        dose_class = _norm_text(evidence.get("dose_class"))
        if dose_class in {"therapeutic_mass", "enzyme_activity", "probiotic_cfu"}:
            return True
    return False


def _has_meaningful_probiotic_dose(product: Dict[str, Any]) -> bool:
    pdata = product.get("probiotic_data") or product.get("probiotic_detail")
    pdata = pdata if isinstance(pdata, dict) else {}
    if _as_float(pdata.get("total_billion_count"), 0.0) > 0.0:
        return True
    if _as_float(pdata.get("total_cfu"), 0.0) > 0.0:
        return True
    for blend in _safe_list(pdata.get("probiotic_blends")):
        if not isinstance(blend, dict):
            continue
        cfu_data = blend.get("cfu_data") if isinstance(blend.get("cfu_data"), dict) else {}
        if _as_float(cfu_data.get("billion_count"), 0.0) > 0.0:
            return True
        if _as_float(cfu_data.get("cfu_count"), 0.0) > 0.0:
            return True
    for row in get_active_ingredients(product):
        if not isinstance(row, dict):
            continue
        if _norm_text(row.get("dose_class")) == "probiotic_cfu" and has_usable_individual_dose(row):
            return True
    for evidence in _safe_list(product.get("product_scoring_evidence")):
        if not isinstance(evidence, dict):
            continue
        if evidence.get("scoreable") is False:
            continue
        if _norm_text(evidence.get("dose_class")) != "probiotic_cfu":
            continue
        dose_value = _as_float(evidence.get("dose_value"), None)
        if dose_value is not None and dose_value > 0:
            return True
    return False


def _omega_mid_mg(dose_payload: Dict[str, Any]) -> Optional[float]:
    metadata = dose_payload.get("metadata") if isinstance(dose_payload, dict) else {}
    if not isinstance(metadata, dict):
        return None
    for key in ("per_day_mid_mg", "total_epa_dha_per_serving"):
        value = _as_float(metadata.get(key), None)
        if value is not None:
            return value
    return None


def classify_dose_zero(
    product: Dict[str, Any],
    *,
    route: str,
    dose_payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Return an audit finding when a route dose score is zero.

    `classification` is either `valid_zero` or `bug_candidate`.
    """
    score = _as_float(dose_payload.get("score") if isinstance(dose_payload, dict) else None, None)
    if score is None or score != 0.0:
        return None

    if _has_unsafe_overdose(product):
        classification, reason = "valid_zero", "unsafe_overdose_zero"
    elif route == "omega" and (_omega_mid_mg(dose_payload) or 0.0) < OMEGA_TRACE_THRESHOLD_MG_DAY:
        classification, reason = "valid_zero", "trace_omega_dose_below_threshold"
    elif route == "probiotic":
        if _has_meaningful_probiotic_dose(product):
            classification, reason = "bug_candidate", "meaningful_disclosed_dose_scored_zero"
        else:
            classification, reason = "valid_zero", "no_meaningful_probiotic_dose"
    elif not _has_meaningful_disclosed_dose(product):
        classification, reason = "valid_zero", "no_meaningful_disclosed_dose"
    else:
        classification, reason = "bug_candidate", "meaningful_disclosed_dose_scored_zero"

    return {
        "dsld_id": product.get("dsld_id") or product.get("id"),
        "brand_name": product.get("brand_name") or product.get("brandName"),
        "product_name": product.get("product_name") or product.get("fullName"),
        "route": route,
        "classification": classification,
        "reason": reason,
        "dose_score": score,
    }


def iter_products(paths: Iterable[str]) -> Iterable[Dict[str, Any]]:
    for pattern in paths:
        for path in glob.glob(pattern):
            try:
                data = json.loads(Path(path).read_text())
            except Exception:
                continue
            rows = data.get("products") if isinstance(data, dict) else data
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict):
                    yield row


def audit_products(products: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for product in products:
        route = class_for_product(product)
        dose_payload = _score_dose_for_route(product, route)
        finding = classify_dose_zero(product, route=route, dose_payload=dose_payload)
        if finding:
            findings.append(finding)
    return findings


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        default=["scripts/products/output_*_enriched/enriched/*.json"],
        help="JSON files or glob patterns containing enriched products.",
    )
    parser.add_argument("--csv-out", help="Optional CSV output path.")
    parser.add_argument("--fail-on-candidates", action="store_true")
    args = parser.parse_args(argv)

    findings = audit_products(iter_products(args.paths))
    counts: Dict[str, int] = {}
    for finding in findings:
        counts[finding["classification"]] = counts.get(finding["classification"], 0) + 1
    print(json.dumps({"total_zero_dose_findings": len(findings), "counts": counts}, indent=2))

    if args.csv_out:
        fieldnames = ["dsld_id", "brand_name", "product_name", "route", "classification", "reason", "dose_score"]
        with open(args.csv_out, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(findings)

    if args.fail_on_candidates and counts.get("bug_candidate", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
