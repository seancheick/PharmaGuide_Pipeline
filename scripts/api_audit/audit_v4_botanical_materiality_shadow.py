#!/usr/bin/env python3
"""Shadow-audit botanical ownership materiality thresholds.

This is a read-only decision surface for changing botanical profile ownership.
It compares the current ScoringClassification v1 botanical materiality threshold
against a candidate threshold without cutting scoring over or changing product
scores. The output answers: "Which products would stop/ start owning the
botanical adapters if materiality were stricter?"
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _path in (str(SCRIPTS_ROOT), str(SCRIPTS_ROOT / "api_audit")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import scoring_input_contract as sic  # noqa: E402
import v4_canary_report as canary  # noqa: E402


DEFAULT_PRODUCTS_ROOT = SCRIPTS_ROOT / "products"
DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "v4_botanical_materiality_shadow"


@contextmanager
def _materiality_fractions(owner_value: float, title_head_value: float, blocker_value: float) -> Iterator[None]:
    original_owner = sic._PROFILE_BOTANICAL_OWNER_MATERIALITY_FRACTION
    original_title_head = sic._PROFILE_BOTANICAL_TITLE_HEAD_MATERIALITY_FRACTION
    original_blocker = sic._PROFILE_NONBOTANICAL_BLOCKER_MATERIALITY_FRACTION
    sic._PROFILE_BOTANICAL_OWNER_MATERIALITY_FRACTION = owner_value
    sic._PROFILE_BOTANICAL_TITLE_HEAD_MATERIALITY_FRACTION = title_head_value
    sic._PROFILE_NONBOTANICAL_BLOCKER_MATERIALITY_FRACTION = blocker_value
    try:
        yield
    finally:
        sic._PROFILE_BOTANICAL_OWNER_MATERIALITY_FRACTION = original_owner
        sic._PROFILE_BOTANICAL_TITLE_HEAD_MATERIALITY_FRACTION = original_title_head
        sic._PROFILE_NONBOTANICAL_BLOCKER_MATERIALITY_FRACTION = original_blocker


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _profile_payload(contract: Dict[str, Any]) -> Dict[str, Any]:
    profiles = _safe_dict(contract.get("profile_eligibility"))
    return _safe_dict(profiles.get("botanical"))


def _botanical_state(
    product: Dict[str, Any],
    owner_threshold: float,
    title_head_threshold: float,
    blocker_threshold: float,
) -> Dict[str, Any]:
    with _materiality_fractions(owner_threshold, title_head_threshold, blocker_threshold):
        contract = sic.build_scoring_classification(product)
    botanical = _profile_payload(contract)
    return {
        "route_module": contract.get("route_module"),
        "route_confidence": contract.get("route_confidence"),
        "eligible": bool(botanical.get("eligible")),
        "owner_type": str(botanical.get("owner_type") or ""),
        "owner_reason_code": str(botanical.get("owner_reason_code") or ""),
        "owner_row_refs": "|".join(str(item) for item in _safe_list(botanical.get("owner_row_refs"))),
        "blocking_row_refs": "|".join(str(item) for item in _safe_list(botanical.get("blocking_row_refs"))),
        "support_row_refs": "|".join(str(item) for item in _safe_list(botanical.get("support_row_refs"))),
    }


def _transition(current: Dict[str, Any], candidate: Dict[str, Any]) -> str:
    if current["eligible"] and not candidate["eligible"]:
        return "candidate_revokes_botanical_ownership"
    if not current["eligible"] and candidate["eligible"]:
        return "candidate_grants_botanical_ownership"
    if current["owner_type"] != candidate["owner_type"]:
        return "owner_type_changed"
    if current["owner_reason_code"] != candidate["owner_reason_code"]:
        return "owner_reason_changed"
    return "unchanged"


def build_rows(
    products: Iterable[Dict[str, Any]],
    *,
    current_owner_threshold: float,
    current_title_head_threshold: float,
    current_blocker_threshold: float,
    candidate_owner_threshold: float,
    candidate_title_head_threshold: float,
    candidate_blocker_threshold: float,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for product in products:
        current = _botanical_state(
            product,
            current_owner_threshold,
            current_title_head_threshold,
            current_blocker_threshold,
        )
        candidate = _botanical_state(
            product,
            candidate_owner_threshold,
            candidate_title_head_threshold,
            candidate_blocker_threshold,
        )
        transition = _transition(current, candidate)
        if transition == "unchanged":
            continue
        rows.append({
            "dsld_id": canary._dsld_id(product),
            "brand_name": product.get("brand_name"),
            "product_name": product.get("product_name") or product.get("fullName"),
            "primary_type": (
                product.get("primary_type")
                or _safe_dict(product.get("supplement_taxonomy")).get("primary_type")
            ),
            "current_owner_threshold": current_owner_threshold,
            "current_title_head_threshold": current_title_head_threshold,
            "current_blocker_threshold": current_blocker_threshold,
            "candidate_owner_threshold": candidate_owner_threshold,
            "candidate_title_head_threshold": candidate_title_head_threshold,
            "candidate_blocker_threshold": candidate_blocker_threshold,
            "transition": transition,
            "current_eligible": current["eligible"],
            "candidate_eligible": candidate["eligible"],
            "current_owner_type": current["owner_type"],
            "candidate_owner_type": candidate["owner_type"],
            "current_owner_reason_code": current["owner_reason_code"],
            "candidate_owner_reason_code": candidate["owner_reason_code"],
            "current_owner_row_refs": current["owner_row_refs"],
            "candidate_owner_row_refs": candidate["owner_row_refs"],
            "current_blocking_row_refs": current["blocking_row_refs"],
            "candidate_blocking_row_refs": candidate["blocking_row_refs"],
            "current_support_row_refs": current["support_row_refs"],
            "candidate_support_row_refs": candidate["support_row_refs"],
            "route_module": current["route_module"],
            "route_confidence": current["route_confidence"],
        })
    return rows


def summarize(
    rows: List[Dict[str, Any]],
    *,
    total_products: int,
    current_owner_threshold: float,
    current_title_head_threshold: float,
    current_blocker_threshold: float,
    candidate_owner_threshold: float,
    candidate_title_head_threshold: float,
    candidate_blocker_threshold: float,
    elapsed_seconds: float,
) -> Dict[str, Any]:
    transitions = Counter(str(row["transition"]) for row in rows)
    owner_transitions = Counter(
        f"{row['current_owner_type']}->{row['candidate_owner_type']}"
        for row in rows
    )
    reason_transitions = Counter(
        f"{row['current_owner_reason_code']}->{row['candidate_owner_reason_code']}"
        for row in rows
    )
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_products": total_products,
        "current_owner_threshold": current_owner_threshold,
        "current_title_head_threshold": current_title_head_threshold,
        "current_blocker_threshold": current_blocker_threshold,
        "candidate_owner_threshold": candidate_owner_threshold,
        "candidate_title_head_threshold": candidate_title_head_threshold,
        "candidate_blocker_threshold": candidate_blocker_threshold,
        "changed_count": len(rows),
        "transition_counts": dict(transitions.most_common()),
        "owner_type_transition_counts": dict(owner_transitions.most_common()),
        "owner_reason_transition_counts": dict(reason_transitions.most_common()),
        "elapsed_seconds": round(elapsed_seconds, 4),
        "ms_per_product": round((elapsed_seconds * 1000.0 / total_products), 4) if total_products else None,
    }


FIELDS = [
    "dsld_id",
    "brand_name",
    "product_name",
    "primary_type",
    "current_owner_threshold",
    "current_title_head_threshold",
    "current_blocker_threshold",
    "candidate_owner_threshold",
    "candidate_title_head_threshold",
    "candidate_blocker_threshold",
    "transition",
    "current_eligible",
    "candidate_eligible",
    "current_owner_type",
    "candidate_owner_type",
    "current_owner_reason_code",
    "candidate_owner_reason_code",
    "current_owner_row_refs",
    "candidate_owner_row_refs",
    "current_blocking_row_refs",
    "candidate_blocking_row_refs",
    "current_support_row_refs",
    "candidate_support_row_refs",
    "route_module",
    "route_confidence",
]


def _write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in FIELDS})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-root", type=Path, default=DEFAULT_PRODUCTS_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--current-owner-threshold", type=float, default=1.0)
    parser.add_argument("--current-title-head-threshold", type=float, default=0.5)
    parser.add_argument("--current-blocker-threshold", type=float, default=0.5)
    parser.add_argument("--candidate-owner-threshold", type=float, default=1.0)
    parser.add_argument("--candidate-title-head-threshold", type=float, default=0.5)
    parser.add_argument("--candidate-blocker-threshold", type=float, default=0.5)
    args = parser.parse_args()

    products = list(canary.build_enriched_index(args.products_root).values())
    started = time.perf_counter()
    rows = build_rows(
        products,
        current_owner_threshold=args.current_owner_threshold,
        current_title_head_threshold=args.current_title_head_threshold,
        current_blocker_threshold=args.current_blocker_threshold,
        candidate_owner_threshold=args.candidate_owner_threshold,
        candidate_title_head_threshold=args.candidate_title_head_threshold,
        candidate_blocker_threshold=args.candidate_blocker_threshold,
    )
    summary = summarize(
        rows,
        total_products=len(products),
        current_owner_threshold=args.current_owner_threshold,
        current_title_head_threshold=args.current_title_head_threshold,
        current_blocker_threshold=args.current_blocker_threshold,
        candidate_owner_threshold=args.candidate_owner_threshold,
        candidate_title_head_threshold=args.candidate_title_head_threshold,
        candidate_blocker_threshold=args.candidate_blocker_threshold,
        elapsed_seconds=time.perf_counter() - started,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    _write_csv(rows, args.out_dir / "changed_products.csv")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
