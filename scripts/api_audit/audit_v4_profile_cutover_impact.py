#!/usr/bin/env python3
"""ScoringClassification v1 profile-selector cutover impact audit.

Read-only audit. It simulates the next cutover step, where generic botanical
and collagen profile selectors consume
``build_scoring_classification(...).profile_eligibility`` instead of their
legacy local selectors.

This does not modify scorer code. It monkeypatches the two generic-module
selector call sites in-process, scores every enriched product before/after, and
writes the score/verdict delta. The report is the decision surface for fixing
or signing remaining profile divergences before any selector cutover lands.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (str(SCRIPTS_ROOT), str(SCRIPTS_ROOT / "api_audit")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scoring_input_contract import build_scoring_classification  # noqa: E402
from scoring_v4.router import class_for_product  # noqa: E402
from score_supplements_v4_shadow import score_product_v4_shadow  # noqa: E402
from scoring_v4.modules.botanical_profile import is_botanical_product  # noqa: E402
from scoring_v4.modules.collagen_profile import is_collagen_product  # noqa: E402
import scoring_v4.modules.generic_dose as generic_dose  # noqa: E402
import scoring_v4.modules.generic_formulation as generic_formulation  # noqa: E402
import v4_shadow_canary_report as canary  # noqa: E402
from audit_v4_profile_consistency import _profile_divergence_reason  # noqa: E402


DEFAULT_PRODUCTS_ROOT = SCRIPTS_ROOT / "products"
DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "v4_profile_cutover_impact"
VERDICT_RANK = {
    "SAFE": 0,
    "POOR": 1,
    "CAUTION": 2,
    "NOT_SCORED": 3,
    "UNSAFE": 4,
    "BLOCKED": 5,
}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _score(product: Dict[str, Any]) -> Dict[str, Any]:
    scored = score_product_v4_shadow(product)
    return {
        "score": _num(scored.get("shadow_score_v4_100")),
        "verdict": scored.get("shadow_score_v4_verdict"),
        "confidence": scored.get("shadow_score_v4_confidence"),
        "module": scored.get("shadow_score_v4_module"),
    }


def _contract_profile(product: Dict[str, Any], profile: str) -> bool:
    contract = build_scoring_classification(product)
    payload = contract.get("profile_eligibility")
    if not isinstance(payload, dict):
        return False
    profile_payload = payload.get(profile)
    return isinstance(profile_payload, dict) and profile_payload.get("eligible") is True


def _contract_botanical_product(product: Dict[str, Any]) -> bool:
    return _contract_profile(product, "botanical")


def _contract_collagen_product(product: Dict[str, Any]) -> bool:
    return _contract_profile(product, "collagen")


@contextmanager
def _contract_profile_selectors() -> Iterator[None]:
    originals = {
        "dose_botanical": generic_dose.is_botanical_product,
        "dose_collagen": generic_dose.is_collagen_product,
        "form_botanical": generic_formulation.is_botanical_product,
        "form_collagen": generic_formulation.is_collagen_product,
    }
    try:
        generic_dose.is_botanical_product = _contract_botanical_product
        generic_dose.is_collagen_product = _contract_collagen_product
        generic_formulation.is_botanical_product = _contract_botanical_product
        generic_formulation.is_collagen_product = _contract_collagen_product
        yield
    finally:
        generic_dose.is_botanical_product = originals["dose_botanical"]
        generic_dose.is_collagen_product = originals["dose_collagen"]
        generic_formulation.is_botanical_product = originals["form_botanical"]
        generic_formulation.is_collagen_product = originals["form_collagen"]


def _verdict_rank(verdict: Any) -> int:
    return VERDICT_RANK.get(str(verdict or "").upper(), -1)


def _less_restrictive(old_verdict: Any, new_verdict: Any) -> bool:
    old_rank = _verdict_rank(old_verdict)
    new_rank = _verdict_rank(new_verdict)
    return old_rank >= 0 and new_rank >= 0 and new_rank < old_rank


def _more_restrictive(old_verdict: Any, new_verdict: Any) -> bool:
    old_rank = _verdict_rank(old_verdict)
    new_rank = _verdict_rank(new_verdict)
    return old_rank >= 0 and new_rank >= 0 and new_rank > old_rank


def _profile_state(product: Dict[str, Any], profile: str, route: str, contract: Dict[str, Any]) -> Dict[str, Any]:
    if profile == "botanical":
        old_eligible = route == "generic" and is_botanical_product(product)
    elif profile == "collagen":
        old_eligible = route == "generic" and is_collagen_product(product)
    else:
        old_eligible = False
    payload = contract.get("profile_eligibility")
    profile_payload = payload.get(profile) if isinstance(payload, dict) else None
    contract_eligible = isinstance(profile_payload, dict) and profile_payload.get("eligible") is True
    evidence = ""
    if isinstance(profile_payload, dict):
        raw_evidence = profile_payload.get("evidence")
        if isinstance(raw_evidence, list):
            evidence = "|".join(str(item) for item in raw_evidence)
        else:
            evidence = str(raw_evidence or "")
    return {
        "old": old_eligible,
        "contract": contract_eligible,
        "diverged": old_eligible != contract_eligible,
        "reason": _profile_divergence_reason(
            product,
            profile,
            contract,
            old_eligible=old_eligible,
            contract_eligible=contract_eligible,
            evidence=evidence,
        ),
    }


def _delta(old_score: float | None, new_score: float | None) -> float | None:
    if old_score is None or new_score is None:
        return None
    return round(new_score - old_score, 4)


def build_rows(products: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    products = list(products)
    old_scores: Dict[str, Dict[str, Any]] = {}
    new_scores: Dict[str, Dict[str, Any]] = {}
    for product in products:
        old_scores[canary._dsld_id(product)] = _score(product)
    with _contract_profile_selectors():
        for product in products:
            new_scores[canary._dsld_id(product)] = _score(product)

    rows: List[Dict[str, Any]] = []
    for product in products:
        dsld_id = canary._dsld_id(product)
        route = class_for_product(product)
        contract = build_scoring_classification(product)
        botanical = _profile_state(product, "botanical", route, contract)
        collagen = _profile_state(product, "collagen", route, contract)
        old = old_scores[dsld_id]
        new = new_scores[dsld_id]
        score_delta = _delta(old["score"], new["score"])
        verdict_changed = old["verdict"] != new["verdict"]
        profile_reasons = [
            f"botanical:{botanical['reason']}" if botanical["diverged"] else "",
            f"collagen:{collagen['reason']}" if collagen["diverged"] else "",
        ]
        rows.append({
            "dsld_id": dsld_id,
            "brand_name": product.get("brand_name"),
            "product_name": product.get("product_name") or product.get("fullName"),
            "primary_type": product.get("primary_type") or canary._safe_dict(product.get("supplement_taxonomy")).get("primary_type"),
            "route_module": route,
            "old_score": old["score"],
            "new_score": new["score"],
            "score_delta": score_delta,
            "abs_score_delta": abs(score_delta) if score_delta is not None else None,
            "old_verdict": old["verdict"],
            "new_verdict": new["verdict"],
            "verdict_changed": verdict_changed,
            "less_restrictive_verdict_flip": _less_restrictive(old["verdict"], new["verdict"]),
            "more_restrictive_verdict_flip": _more_restrictive(old["verdict"], new["verdict"]),
            "botanical_old": botanical["old"],
            "botanical_contract": botanical["contract"],
            "botanical_reason": botanical["reason"],
            "collagen_old": collagen["old"],
            "collagen_contract": collagen["contract"],
            "collagen_reason": collagen["reason"],
            "profile_diverged": botanical["diverged"] or collagen["diverged"],
            "profile_reasons": "|".join(reason for reason in profile_reasons if reason),
        })
    return rows


def summarize(rows: List[Dict[str, Any]], *, elapsed_seconds: float) -> Dict[str, Any]:
    changed = [row for row in rows if row.get("old_score") != row.get("new_score") or row.get("old_verdict") != row.get("new_verdict")]
    verdict_flips = [row for row in rows if row.get("verdict_changed")]
    less_restrictive = [row for row in rows if row.get("less_restrictive_verdict_flip")]
    more_restrictive = [row for row in rows if row.get("more_restrictive_verdict_flip")]
    large_score_delta = [
        row for row in changed
        if row.get("abs_score_delta") is not None and float(row["abs_score_delta"]) >= 5.0
    ]
    by_reason = defaultdict(Counter)
    for row in changed:
        if row.get("botanical_old") != row.get("botanical_contract"):
            by_reason["botanical"][str(row.get("botanical_reason"))] += 1
        if row.get("collagen_old") != row.get("collagen_contract"):
            by_reason["collagen"][str(row.get("collagen_reason"))] += 1
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_products": len(rows),
        "profile_diverged_count": sum(1 for row in rows if row.get("profile_diverged")),
        "score_or_verdict_changed_count": len(changed),
        "verdict_flip_count": len(verdict_flips),
        "less_restrictive_verdict_flip_count": len(less_restrictive),
        "more_restrictive_verdict_flip_count": len(more_restrictive),
        "large_score_delta_ge_5_count": len(large_score_delta),
        "old_verdict_counts": dict(Counter(str(row.get("old_verdict")) for row in rows).most_common()),
        "new_verdict_counts": dict(Counter(str(row.get("new_verdict")) for row in rows).most_common()),
        "changed_by_profile_reason": {
            profile: dict(counter.most_common())
            for profile, counter in sorted(by_reason.items())
        },
        "elapsed_seconds": round(elapsed_seconds, 4),
        "ms_per_product": round((elapsed_seconds * 1000.0 / len(rows)), 4) if rows else None,
        "ready_for_cutover": not verdict_flips and not large_score_delta,
    }


def _write_csv(rows: List[Dict[str, Any]], path: Path, fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


FIELDS = [
    "dsld_id",
    "brand_name",
    "product_name",
    "primary_type",
    "route_module",
    "old_score",
    "new_score",
    "score_delta",
    "abs_score_delta",
    "old_verdict",
    "new_verdict",
    "verdict_changed",
    "less_restrictive_verdict_flip",
    "more_restrictive_verdict_flip",
    "botanical_old",
    "botanical_contract",
    "botanical_reason",
    "collagen_old",
    "collagen_contract",
    "collagen_reason",
    "profile_diverged",
    "profile_reasons",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-root", type=Path, default=DEFAULT_PRODUCTS_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    enriched_index = canary.build_enriched_index(args.products_root)
    products = list(enriched_index.values())
    started = time.perf_counter()
    rows = build_rows(products)
    summary = summarize(rows, elapsed_seconds=time.perf_counter() - started)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    _write_csv(rows, args.out_dir / "all_products.csv", FIELDS)
    _write_csv(
        [row for row in rows if row.get("score_delta") not in {None, 0.0} or row.get("verdict_changed")],
        args.out_dir / "score_or_verdict_changes.csv",
        FIELDS,
    )
    _write_csv([row for row in rows if row.get("verdict_changed")], args.out_dir / "verdict_flips.csv", FIELDS)

    print(json.dumps(summary, indent=2))
    return 0 if summary["ready_for_cutover"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
