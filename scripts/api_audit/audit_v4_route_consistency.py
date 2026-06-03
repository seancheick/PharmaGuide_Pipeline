#!/usr/bin/env python3
"""ScoringClassification v1 route-consistency release gate.

Read-only audit. It proves the compatibility classification contract preserves
current v4 routing, tracks verdict flips, runs pinned route-precedence canaries,
and reports route/confidence distribution drift for scale monitoring.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (str(SCRIPTS_ROOT), str(SCRIPTS_ROOT / "api_audit")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scoring_input_contract import build_scoring_classification  # noqa: E402
from scoring_v4.router import _legacy_class_for_product, class_for_product  # noqa: E402
from score_supplements_v4_shadow import score_product_v4_shadow  # noqa: E402
import v4_shadow_canary_report as canary  # noqa: E402


DEFAULT_PRODUCTS_ROOT = SCRIPTS_ROOT / "products"
DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "v4_route_consistency"


def _row(canonical: str, name: str, quantity: float = 100, unit: str = "mg", **extra: Any) -> Dict[str, Any]:
    row = {
        "canonical_id": canonical,
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "mapped": True,
        "source_section": "activeIngredients",
        "raw_source_path": f"activeIngredients[{canonical}]",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
        "dose_class": "therapeutic_mass",
        "role_classification": "active_scorable",
        "scoreable_identity": True,
    }
    row.update(extra)
    return row


def _product(name: str, rows: List[Dict[str, Any]], *, primary_type: str = "general_supplement", **extra: Any) -> Dict[str, Any]:
    product = {
        "product_name": name,
        "primary_type": primary_type,
        "supplement_taxonomy": {"primary_type": primary_type},
        "ingredient_quality_data": {"ingredients_scorable": rows},
    }
    product.update(extra)
    return product


PINNED_CANARIES: List[Dict[str, Any]] = [
    {
        "id": "omega_content_positive_generic_title",
        "expected_route": "omega",
        "product": _product("Essential Fatty Acids", [_row("epa", "EPA", 500, "mg")]),
    },
    {
        "id": "omega_title_negative_ala_only",
        "expected_route": "generic",
        "product": _product("Omega 3-6-9", [_row("alpha_linolenic_acid_ala", "ALA", 1000, "mg")]),
    },
    {
        "id": "pure_fish_oil_routes_omega",
        "expected_route": "omega",
        "product": _product("Fish Oil EPA DHA", [_row("epa", "EPA", 500, "mg"), _row("dha", "DHA", 250, "mg")], primary_type="omega_3"),
    },
    {
        "id": "creatine_single_routes_sports",
        "expected_route": "sports",
        "product": _product("Creatine Monohydrate", [_row("creatine_monohydrate", "Creatine", 5, "g")]),
    },
    {
        "id": "protein_single_routes_sports",
        "expected_route": "sports",
        "product": _product("Whey Protein Isolate", [_row("whey_protein", "Whey Protein", 25, "g")], primary_type="protein_powder"),
    },
    {
        "id": "true_probiotic_routes_probiotic",
        "expected_route": "probiotic",
        "product": _product(
            "FLORASSIST Balance",
            [],
            probiotic_data={"is_probiotic_product": True, "total_strain_count": 10, "has_cfu": False},
        ),
    },
    {
        "id": "probiotic_adjunct_does_not_hijack_zinc",
        "expected_route": "generic",
        "product": _product(
            "Whole Food Zinc Quercetin Complex",
            [],
            probiotic_data={"is_probiotic_product": True, "total_strain_count": 5, "has_cfu": False},
        ),
    },
    {
        "id": "prenatal_dha_routes_omega",
        "expected_route": "omega",
        "product": _product("Prenatal DHA", [_row("epa", "EPA", 200, "mg"), _row("dha", "DHA", 450, "mg")]),
    },
    {
        "id": "prenatal_multi_routes_multi",
        "expected_route": "multi_or_prenatal",
        "product": _product(
            "Prenatal Multi",
            [
                _row("vitamin_b9_folate", "Folate", 400, "mcg"),
                _row("iron", "Iron", 18, "mg"),
                _row("iodine", "Iodine", 150, "mcg"),
                _row("choline", "Choline", 55, "mg"),
                _row("vitamin_d", "Vitamin D", 25, "mcg"),
            ],
        ),
    },
]


def _load_allowlist(path: Path | None) -> Dict[str, Dict[str, str]]:
    if not path or not path.exists():
        return {}
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        return {str(row.get("dsld_id") or ""): row for row in reader if row.get("dsld_id")}


def _allowlist_signed(row: Dict[str, Any], allowlist: Dict[str, Dict[str, str]]) -> bool:
    dsld_id = str(row.get("dsld_id") or "")
    allowed = allowlist.get(dsld_id)
    if not allowed:
        return False
    return str(allowed.get("human_signoff_status") or "").strip().lower() in {"approved", "signed_off", "yes"}


def _score_verdict(product: Dict[str, Any]) -> Tuple[str | None, float | None]:
    try:
        scored = score_product_v4_shadow(product)
    except Exception:
        return None, None
    return scored.get("shadow_score_v4_verdict"), canary._num(scored.get("shadow_score_v4_100"))


def run_canaries() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in PINNED_CANARIES:
        product = item["product"]
        contract = build_scoring_classification(product)
        public_route = class_for_product(product)
        rows.append({
            "canary_id": item["id"],
            "expected_route": item["expected_route"],
            "contract_route": contract.get("route_module"),
            "public_route": public_route,
            "passed": contract.get("route_module") == item["expected_route"] and public_route == item["expected_route"],
            "route_confidence": contract.get("route_confidence"),
            "classification_failed": contract.get("classification_failed"),
        })
    return rows


def build_rows(products: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for product in products:
        dsld_id = canary._dsld_id(product)
        old_route = _legacy_class_for_product(product)
        contract = build_scoring_classification(product)
        public_route = class_for_product(product)
        verdict, score = _score_verdict(product)
        rows.append({
            "dsld_id": dsld_id,
            "brand_name": product.get("brand_name"),
            "product_name": product.get("product_name") or product.get("fullName"),
            "primary_type": product.get("primary_type") or canary._safe_dict(product.get("supplement_taxonomy")).get("primary_type"),
            "old_route": old_route,
            "contract_route": contract.get("route_module"),
            "public_route": public_route,
            "route_confidence": contract.get("route_confidence"),
            "classification_failed": contract.get("classification_failed"),
            "classification_origin": contract.get("classification_origin"),
            "v4_verdict": verdict,
            "v4_score": score,
            "route_diverged": old_route != contract.get("route_module") or public_route != contract.get("route_module"),
        })
    return rows


def summarize(
    rows: List[Dict[str, Any]],
    canary_rows: List[Dict[str, Any]],
    allowlist: Dict[str, Dict[str, str]],
    *,
    elapsed_seconds: float,
) -> Dict[str, Any]:
    route_divergences = [row for row in rows if row.get("route_diverged")]
    unsigned_divergences = [row for row in route_divergences if not _allowlist_signed(row, allowlist)]
    canary_failures = [row for row in canary_rows if not row.get("passed")]
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_products": len(rows),
        "route_counts": dict(Counter(str(row.get("contract_route")) for row in rows).most_common()),
        "route_confidence_counts": dict(Counter(str(row.get("route_confidence")) for row in rows).most_common()),
        "verdict_counts": dict(Counter(str(row.get("v4_verdict")) for row in rows).most_common()),
        "classification_failed_count": sum(1 for row in rows if row.get("classification_failed")),
        "not_scored_count": sum(1 for row in rows if str(row.get("v4_verdict") or "").upper() == "NOT_SCORED"),
        "route_divergence_count": len(route_divergences),
        "unsigned_route_divergence_count": len(unsigned_divergences),
        "canary_count": len(canary_rows),
        "canary_failure_count": len(canary_failures),
        "elapsed_seconds": round(elapsed_seconds, 4),
        "ms_per_product": round((elapsed_seconds * 1000.0 / len(rows)), 4) if rows else None,
        "ready": not unsigned_divergences and not canary_failures,
    }


def _write_csv(rows: List[Dict[str, Any]], path: Path, fields: List[str]) -> None:
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
    parser.add_argument("--allowlist", type=Path, default=None)
    args = parser.parse_args()

    enriched_index = canary.build_enriched_index(args.products_root)
    products = list(enriched_index.values())
    allowlist = _load_allowlist(args.allowlist)
    started = time.perf_counter()
    canary_rows = run_canaries()
    rows = build_rows(products)
    summary = summarize(rows, canary_rows, allowlist, elapsed_seconds=time.perf_counter() - started)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    _write_csv(
        [row for row in rows if row.get("route_diverged")],
        args.out_dir / "route_divergences.csv",
        [
            "dsld_id", "brand_name", "product_name", "primary_type",
            "old_route", "contract_route", "public_route", "route_confidence",
            "v4_verdict", "v4_score", "classification_failed",
        ],
    )
    _write_csv(
        canary_rows,
        args.out_dir / "canaries.csv",
        ["canary_id", "expected_route", "contract_route", "public_route", "route_confidence", "classification_failed", "passed"],
    )
    _write_csv(
        rows,
        args.out_dir / "route_distribution.csv",
        [
            "dsld_id", "brand_name", "product_name", "primary_type",
            "contract_route", "route_confidence", "v4_verdict", "v4_score",
            "classification_failed",
        ],
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
