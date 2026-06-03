#!/usr/bin/env python3
"""ScoringClassification v1 profile-consistency audit.

Read-only audit. It compares today's local profile selectors against
``build_scoring_classification(...).profile_eligibility`` before any scoring
module consumes the contract for profile decisions.

This is intentionally stricter than a score-delta audit: profile eligibility
can change which dose/formulation adapter runs without changing the top-level
route. The audit writes a frozen per-product baseline and fails until every
profile divergence is either fixed or explicitly allowlisted.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (str(SCRIPTS_ROOT), str(SCRIPTS_ROOT / "api_audit")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scoring_input_contract import build_scoring_classification  # noqa: E402
from scoring_v4.modules.botanical_profile import is_botanical_product  # noqa: E402
from scoring_v4.modules.collagen_profile import is_collagen_product  # noqa: E402
from scoring_v4.router import _legacy_class_for_product, class_for_product  # noqa: E402
from score_supplements_v4_shadow import score_product_v4_shadow  # noqa: E402
import v4_shadow_canary_report as canary  # noqa: E402


DEFAULT_PRODUCTS_ROOT = SCRIPTS_ROOT / "products"
DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "v4_profile_consistency"
PROFILE_NAMES = ("botanical", "collagen", "omega", "probiotic", "sports")


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
        "canary_id": "botanical_positive_ashwagandha",
        "profile": "botanical",
        "product": _product(
            "Ashwagandha Root Extract",
            [
                _row(
                    "ashwagandha",
                    "Ashwagandha Root Extract",
                    600,
                    "mg",
                    raw_taxonomy={"category": "botanical", "forms": [{"name": "root extract", "category": "botanical"}]},
                )
            ],
        ),
    },
    {
        "canary_id": "botanical_negative_l_theanine",
        "profile": "botanical",
        "product": _product(
            "L-Theanine 200 mg",
            [_row("l_theanine", "L-Theanine", 200, "mg", raw_taxonomy={"category": "amino acid"})],
        ),
    },
    {
        "canary_id": "botanical_negative_zinc_with_elderberry",
        "profile": "botanical",
        "product": _product(
            "Zinc with Elderberry",
            [
                _row("zinc", "Zinc", 30, "mg", raw_taxonomy={"category": "mineral"}),
                _row("elderberry", "Elderberry", 50, "mg", raw_taxonomy={"category": "botanical"}),
            ],
            primary_type="single_mineral",
        ),
    },
    {
        "canary_id": "collagen_positive_peptides",
        "profile": "collagen",
        "product": _product("Collagen Peptides", [_row("collagen", "Collagen Peptides", 10, "g")]),
    },
    {
        "canary_id": "collagen_negative_token_addon",
        "profile": "collagen",
        "product": _product(
            "Magnesium with Collagen",
            [_row("magnesium", "Magnesium", 400, "mg"), _row("collagen", "Collagen", 50, "mg")],
        ),
    },
    {
        "canary_id": "omega_positive_epa_dha",
        "profile": "omega",
        "product": _product("Fish Oil EPA DHA", [_row("epa", "EPA", 500, "mg"), _row("dha", "DHA", 250, "mg")]),
    },
    {
        "canary_id": "omega_negative_ala_only",
        "profile": "omega",
        "product": _product("Omega 3-6-9", [_row("alpha_linolenic_acid_ala", "ALA", 1000, "mg")]),
    },
]


def _load_allowlist(path: Path | None) -> Dict[str, Dict[str, str]]:
    if not path or not path.exists():
        return {}
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        return {f"{row.get('dsld_id')}:{row.get('profile')}": row for row in reader if row.get("dsld_id") and row.get("profile")}


def _allowlist_signed(row: Dict[str, Any], allowlist: Dict[str, Dict[str, str]]) -> bool:
    allowed = allowlist.get(f"{row.get('dsld_id')}:{row.get('profile')}")
    if not allowed:
        return False
    return str(allowed.get("human_signoff_status") or "").strip().lower() in {"approved", "signed_off", "yes"}


def _score_verdict(product: Dict[str, Any]) -> tuple[str | None, float | None]:
    try:
        scored = score_product_v4_shadow(product)
    except Exception:
        return None, None
    return scored.get("shadow_score_v4_verdict"), canary._num(scored.get("shadow_score_v4_100"))


def _contract_profile(contract: Dict[str, Any], profile: str) -> bool:
    payload = contract.get("profile_eligibility")
    if not isinstance(payload, dict):
        return False
    profile_payload = payload.get(profile)
    return isinstance(profile_payload, dict) and profile_payload.get("eligible") is True


def _old_profile_eligibility(product: Dict[str, Any], profile: str, old_route: str) -> bool:
    if profile == "botanical":
        return old_route == "generic" and bool(is_botanical_product(product))
    if profile == "collagen":
        return old_route == "generic" and bool(is_collagen_product(product))
    if profile in {"omega", "probiotic", "sports"}:
        return old_route == profile
    return False


def _profile_evidence(contract: Dict[str, Any], profile: str) -> str:
    payload = contract.get("profile_eligibility")
    if not isinstance(payload, dict):
        return ""
    profile_payload = payload.get(profile)
    if not isinstance(profile_payload, dict):
        return ""
    evidence = profile_payload.get("evidence")
    if isinstance(evidence, list):
        return "|".join(str(item) for item in evidence)
    return str(evidence or "")


def _profile_payload(contract: Dict[str, Any], profile: str) -> Dict[str, Any]:
    payload = contract.get("profile_eligibility")
    if not isinstance(payload, dict):
        return {}
    profile_payload = payload.get(profile)
    return profile_payload if isinstance(profile_payload, dict) else {}


def _profile_eligible_row_count(contract: Dict[str, Any], profile: str) -> int:
    value = _profile_payload(contract, profile).get("eligible_row_count")
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _active_row_count(product: Dict[str, Any]) -> int:
    iqd = product.get("ingredient_quality_data")
    if not isinstance(iqd, dict):
        return 0
    rows = iqd.get("ingredients_scorable")
    return len(rows) if isinstance(rows, list) else 0


def _contract_row_count(contract: Dict[str, Any]) -> int:
    rows = contract.get("ingredients")
    return len(rows) if isinstance(rows, list) else 0


def _profile_divergence_direction(old_eligible: bool, contract_eligible: bool) -> str:
    if old_eligible == contract_eligible:
        return "aligned"
    return "contract_grants" if contract_eligible else "contract_revokes"


def _profile_divergence_reason(
    product: Dict[str, Any],
    profile: str,
    contract: Dict[str, Any],
    *,
    old_eligible: bool,
    contract_eligible: bool,
    evidence: str,
) -> str:
    if old_eligible == contract_eligible:
        return "aligned"

    direction = _profile_divergence_direction(old_eligible, contract_eligible)
    active_count = _active_row_count(product)
    contract_count = _contract_row_count(contract)
    eligible_count = _profile_eligible_row_count(contract, profile)

    if profile == "botanical":
        if direction == "contract_grants":
            if contract_count > active_count:
                return "contract_grants_recovered_botanical_rows"
            if "standardized_botanical_source_db" in evidence:
                return "contract_grants_standardized_botanical_source"
            if "raw_taxonomy_botanical" in evidence or "botanical_source_form" in evidence or "botanical_source_text" in evidence:
                return "contract_grants_positive_botanical_source"
            return "contract_grants_botanical_unclassified"
        if not evidence or eligible_count == 0:
            return "contract_revokes_reference_membership_without_source_evidence"
        return "contract_revokes_role_materiality_or_intent"

    if profile == "collagen":
        if direction == "contract_grants":
            if contract_count > active_count:
                return "contract_grants_recovered_collagen_rows"
            return "contract_grants_collagen_identity"
        if not evidence or eligible_count == 0:
            return "contract_revokes_missing_collagen_identity"
        return "contract_revokes_collagen_mass_or_product_intent"

    return f"{direction}_{profile}"


def _profile_row(
    product: Dict[str, Any],
    profile: str,
    contract: Dict[str, Any],
    *,
    old_route: str,
    public_route: str,
    verdict: str | None,
    score: float | None,
) -> Dict[str, Any]:
    old_eligible = _old_profile_eligibility(product, profile, old_route)
    contract_eligible = _contract_profile(contract, profile)
    classification_failed = bool(contract.get("classification_failed"))
    evidence = _profile_evidence(contract, profile)
    direction = _profile_divergence_direction(old_eligible, contract_eligible)
    return {
        "dsld_id": canary._dsld_id(product),
        "brand_name": product.get("brand_name"),
        "product_name": product.get("product_name") or product.get("fullName"),
        "primary_type": product.get("primary_type") or canary._safe_dict(product.get("supplement_taxonomy")).get("primary_type"),
        "profile": profile,
        "old_route": old_route,
        "public_route": public_route,
        "old_profile_eligible": old_eligible,
        "contract_profile_eligible": contract_eligible,
        "profile_diverged": old_eligible != contract_eligible,
        "profile_divergence_direction": direction,
        "profile_divergence_reason": _profile_divergence_reason(
            product,
            profile,
            contract,
            old_eligible=old_eligible,
            contract_eligible=contract_eligible,
            evidence=evidence,
        ),
        "active_row_count": _active_row_count(product),
        "contract_row_count": _contract_row_count(contract),
        "contract_eligible_row_count": _profile_eligible_row_count(contract, profile),
        "classification_failed": classification_failed,
        "classification_failure_reason": contract.get("classification_failure_reason"),
        "failure_granted_profile": classification_failed and not old_eligible and contract_eligible,
        "failure_revoked_profile": classification_failed and old_eligible and not contract_eligible,
        "route_confidence": contract.get("route_confidence"),
        "profile_evidence": evidence,
        "v4_verdict": verdict,
        "v4_score": score,
    }


def build_rows(products: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for product in products:
        old_route = _legacy_class_for_product(product)
        public_route = class_for_product(product)
        contract = build_scoring_classification(product)
        verdict, score = _score_verdict(product)
        for profile in PROFILE_NAMES:
            rows.append(_profile_row(
                product,
                profile,
                contract,
                old_route=old_route,
                public_route=public_route,
                verdict=verdict,
                score=score,
            ))
    return rows


def run_canaries() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in PINNED_CANARIES:
        product = item["product"]
        profile = item["profile"]
        old_route = _legacy_class_for_product(product)
        contract = build_scoring_classification(product)
        row = _profile_row(
            product,
            profile,
            contract,
            old_route=old_route,
            public_route=class_for_product(product),
            verdict=None,
            score=None,
        )
        row["canary_id"] = item["canary_id"]
        row["passed"] = not row["profile_diverged"]
        rows.append(row)
    return rows


def summarize(
    rows: List[Dict[str, Any]],
    canary_rows: List[Dict[str, Any]],
    allowlist: Dict[str, Dict[str, str]],
    *,
    elapsed_seconds: float,
) -> Dict[str, Any]:
    divergences = [row for row in rows if row.get("profile_diverged")]
    unsigned_divergences = [row for row in divergences if not _allowlist_signed(row, allowlist)]
    failed_rows = [row for row in rows if row.get("classification_failed")]
    failure_grants = [row for row in rows if row.get("failure_granted_profile")]
    failure_revokes = [row for row in rows if row.get("failure_revoked_profile")]
    canary_failures = [row for row in canary_rows if not row.get("passed")]
    by_profile = defaultdict(Counter)
    by_reason = Counter()
    by_profile_reason = defaultdict(Counter)
    for row in rows:
        profile = str(row.get("profile"))
        by_profile[profile]["old_true"] += bool(row.get("old_profile_eligible"))
        by_profile[profile]["contract_true"] += bool(row.get("contract_profile_eligible"))
        by_profile[profile]["diverged"] += bool(row.get("profile_diverged"))
        if row.get("profile_diverged"):
            reason = str(row.get("profile_divergence_reason") or "unknown")
            by_reason[reason] += 1
            by_profile_reason[profile][reason] += 1
    product_count = len(rows) // len(PROFILE_NAMES) if len(rows) >= len(PROFILE_NAMES) else len(rows)
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_products": product_count,
        "total_profile_rows": len(rows),
        "profile_counts": {profile: dict(counter) for profile, counter in sorted(by_profile.items())},
        "profile_divergence_reasons": dict(by_reason.most_common()),
        "profile_divergence_reasons_by_profile": {
            profile: dict(counter.most_common())
            for profile, counter in sorted(by_profile_reason.items())
        },
        "profile_divergence_count": len(divergences),
        "unsigned_profile_divergence_count": len(unsigned_divergences),
        "classification_failed_count": len(failed_rows),
        "failure_granted_profile_count": len(failure_grants),
        "failure_revoked_profile_count": len(failure_revokes),
        "canary_count": len(canary_rows),
        "canary_failure_count": len(canary_failures),
        "verdict_counts": dict(Counter(str(row.get("v4_verdict")) for row in rows if row.get("profile") == "botanical").most_common()),
        "elapsed_seconds": round(elapsed_seconds, 4),
        "ms_per_product": round((elapsed_seconds * 1000.0 / product_count), 4) if product_count else None,
        "ready": (
            not unsigned_divergences
            and not failed_rows
            and not failure_grants
            and not failure_revokes
            and not canary_failures
        ),
    }


def _write_csv(rows: List[Dict[str, Any]], path: Path, fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _reason_summary_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    examples: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    for row in rows:
        if not row.get("profile_diverged"):
            continue
        key = (
            str(row.get("profile")),
            str(row.get("profile_divergence_direction")),
            str(row.get("profile_divergence_reason")),
        )
        grouped[key]["count"] += 1
        grouped[key][str(row.get("v4_verdict"))] += 1
        examples.setdefault(key, row)

    output: List[Dict[str, Any]] = []
    for key, counter in sorted(grouped.items(), key=lambda item: (-item[1]["count"], item[0])):
        example = examples[key]
        output.append({
            "profile": key[0],
            "direction": key[1],
            "reason": key[2],
            "count": counter["count"],
            "safe_count": counter.get("SAFE", 0),
            "caution_count": counter.get("CAUTION", 0),
            "poor_count": counter.get("POOR", 0),
            "not_scored_count": counter.get("NOT_SCORED", 0),
            "example_dsld_id": example.get("dsld_id"),
            "example_product_name": example.get("product_name"),
            "example_profile_evidence": example.get("profile_evidence"),
        })
    return output


FIELDS = [
    "dsld_id",
    "brand_name",
    "product_name",
    "primary_type",
    "profile",
    "old_route",
    "public_route",
    "old_profile_eligible",
    "contract_profile_eligible",
    "profile_diverged",
    "profile_divergence_direction",
    "profile_divergence_reason",
    "active_row_count",
    "contract_row_count",
    "contract_eligible_row_count",
    "classification_failed",
    "classification_failure_reason",
    "failure_granted_profile",
    "failure_revoked_profile",
    "route_confidence",
    "profile_evidence",
    "v4_verdict",
    "v4_score",
]


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
    _write_csv(rows, args.out_dir / "frozen_profile_baseline.csv", FIELDS)
    _write_csv([row for row in rows if row.get("profile_diverged")], args.out_dir / "profile_divergences.csv", FIELDS)
    _write_csv(
        _reason_summary_rows(rows),
        args.out_dir / "profile_divergence_reason_summary.csv",
        [
            "profile",
            "direction",
            "reason",
            "count",
            "safe_count",
            "caution_count",
            "poor_count",
            "not_scored_count",
            "example_dsld_id",
            "example_product_name",
            "example_profile_evidence",
        ],
    )
    _write_csv(canary_rows, args.out_dir / "canaries.csv", ["canary_id", "passed", *FIELDS])

    print(json.dumps(summary, indent=2))
    return 0 if summary["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
