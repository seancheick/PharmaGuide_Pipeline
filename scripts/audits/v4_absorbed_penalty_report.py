#!/usr/bin/env python3
"""Report v4 penalties hidden by positive credit above a dimension cap.

This audit compares the current dimension order::

    clamp(0, cap, gross_positive_credit - penalties)

with the policy alternative::

    clamp(0, cap, gross_positive_credit) - penalties

It does not change scoring.  The report exists to support the later policy
decision about which penalty classes may consume positive headroom.
"""

from __future__ import annotations

import argparse
import copy
import csv
import glob
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


RECONSTRUCTION_TOLERANCE = 0.011


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _numeric_sum(values: Iterable[Any], *, magnitude: bool = False) -> float:
    total = 0.0
    for value in values:
        number = _finite_number(value)
        if number is None:
            continue
        total += abs(number) if magnitude else number
    return total


def _round(value: float) -> float:
    return round(float(value), 4)


def _penalty_policy_class(penalty_key: str) -> str:
    normalized = penalty_key.casefold()
    if "false_allergen_free" in normalized:
        return "never_absorbable_material_defect"
    if "proprietary_blend_opacity" in normalized or "marketing_claims" in normalized:
        return "potentially_absorbable_soft_debt"
    return "requires_policy_review"


def analyze_dimension(dimension: dict[str, Any]) -> dict[str, Any] | None:
    """Return an absorbed-penalty finding, or ``None`` when no debt is hidden."""
    components = dimension.get("components")
    penalties = dimension.get("penalties")
    if not isinstance(components, dict) or not isinstance(penalties, dict):
        return None

    gross_positive = _numeric_sum(components.values())
    penalty_rows = []
    for key in sorted(penalties):
        amount = _finite_number(penalties[key])
        if amount is None or abs(amount) <= 1e-9:
            continue
        penalty_rows.append(
            {
                "type": str(key),
                "amount": _round(abs(amount)),
                "policy_class": _penalty_policy_class(str(key)),
                "absorbed_amount": None,
            }
        )
    if not penalty_rows:
        return None

    cap = _finite_number(dimension.get("max"))
    current_score = _finite_number(dimension.get("score"))
    if cap is None or cap <= 0 or current_score is None:
        return None

    total_penalty = sum(row["amount"] for row in penalty_rows)
    current_reconstructed = max(0.0, min(cap, gross_positive - total_penalty))
    if abs(current_reconstructed - current_score) > RECONSTRUCTION_TOLERANCE:
        if gross_positive > cap:
            raise ValueError(
                "Cannot safely model a penalized dimension with positive headroom: "
                f"gross={gross_positive}, penalties={total_penalty}, cap={cap}, "
                f"score={current_score}, reconstructed={current_reconstructed}"
            )
        return None

    alternative_score = max(0.0, min(cap, gross_positive) - total_penalty)
    absorbed = current_score - alternative_score
    if absorbed <= RECONSTRUCTION_TOLERANCE:
        return None

    policy_classes = {row["policy_class"] for row in penalty_rows}
    if "never_absorbable_material_defect" in policy_classes:
        overall_policy = "contains_never_absorbable_material_defect"
    elif policy_classes == {"potentially_absorbable_soft_debt"}:
        overall_policy = "potentially_absorbable_soft_debt"
    else:
        overall_policy = "requires_policy_review"

    if len(penalty_rows) == 1:
        attribution = "single_penalty_exact"
        penalty_rows[0]["absorbed_amount"] = _round(absorbed)
    else:
        # Current math subtracts one combined magnitude, so assigning shared
        # headroom to a specific penalty would invent an ordering that does not
        # exist. Keep the total exact and the per-penalty attribution explicit.
        attribution = "shared_headroom_not_uniquely_attributable"

    return {
        "gross_positive_credit": _round(gross_positive),
        "dimension_cap": _round(cap),
        "positive_headroom": _round(max(0.0, gross_positive - cap)),
        "penalties": penalty_rows,
        "total_penalty_amount": _round(total_penalty),
        "absorbed_amount": _round(absorbed),
        "current_dimension_score": _round(current_score),
        "alternative_dimension_score": _round(alternative_score),
        "penalty_policy_class": overall_policy,
        "absorption_attribution": attribution,
    }


def _pre_cap_pillar_scores(product: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for name, pillar in (product.get("quality_pillars_v4") or {}).items():
        if not isinstance(pillar, dict):
            continue
        components = pillar.get("components")
        before_cap = (
            components.get("score_before_public_cap")
            if isinstance(components, dict)
            else None
        )
        value = _finite_number(before_cap)
        if value is None:
            value = _finite_number(pillar.get("score"))
        if value is not None:
            scores[str(name)] = value
    return scores


def _alternative_public_pillar_score(
    product: dict[str, Any],
    dimension_name: str,
    alternative_dimension_score: float,
    dimension_cap: float,
) -> float:
    pillar = (product.get("quality_pillars_v4") or {}).get(dimension_name) or {}
    weight = _finite_number(pillar.get("max"))
    if weight is None:
        raise ValueError(f"Missing public pillar weight for {dimension_name}")

    components = pillar.get("components") or {}
    reference = _finite_number(components.get("reference"))
    denominator = reference if reference and dimension_name in {
        "formulation",
        "dose",
        "evidence",
    } else dimension_cap
    return round(
        max(0.0, min(weight, (alternative_dimension_score / denominator) * weight)),
        1,
    )


def _quality_tier(score: float) -> str:
    # Keep the report on the same configured thresholds as production rather
    # than maintaining a second tier table in audit code. Read the canonical
    # config directly so this standalone script does not depend on PYTHONPATH.
    config_path = (
        Path(__file__).resolve().parents[1]
        / "scoring_v4"
        / "config"
        / "quality_score.json"
    )
    bands = json.loads(config_path.read_text(encoding="utf-8"))["tiers"]
    for band in bands:
        if score >= float(band["min"]):
            return str(band["name"])
    return str(bands[-1]["name"])


def _alternative_public_score(
    product: dict[str, Any],
    dimension_name: str,
    finding: dict[str, Any],
) -> float | None:
    current = _finite_number(product.get("quality_score_v4_100"))
    if current is None:
        return None

    pre_cap_scores = _pre_cap_pillar_scores(product)
    cap_payload = product.get("quality_score_cap_v4")
    cap = (
        _finite_number(cap_payload.get("cap"))
        if isinstance(cap_payload, dict)
        else None
    )
    reconstructed_current = round(sum(pre_cap_scores.values()), 1)
    if cap is not None:
        reconstructed_current = min(reconstructed_current, cap)
    if abs(reconstructed_current - current) > RECONSTRUCTION_TOLERANCE:
        raise ValueError(
            "Cannot safely reconstruct the current public score: "
            f"reported={current}, reconstructed={reconstructed_current}"
        )

    if dimension_name not in pre_cap_scores:
        raise ValueError(f"Missing public pillar for affected dimension {dimension_name}")
    pre_cap_scores[dimension_name] = _alternative_public_pillar_score(
        product,
        dimension_name,
        finding["alternative_dimension_score"],
        finding["dimension_cap"],
    )
    alternative = round(sum(pre_cap_scores.values()), 1)

    if cap is not None:
        alternative = min(alternative, cap)
    return round(max(0.0, min(100.0, alternative)), 1)


def _input_fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\0")
    return digest.hexdigest()


def build_report(paths: list[Path]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    products_scanned = 0
    penalized_dimensions = 0

    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{path}: expected a top-level product list")
        for product in payload:
            if not isinstance(product, dict):
                continue
            products_scanned += 1
            module_breakdown = product.get("_v4_module_breakdown") or {}
            dimensions = module_breakdown.get("dimensions") or {}
            for dimension_name, dimension in dimensions.items():
                if not isinstance(dimension, dict):
                    continue
                if _numeric_sum((dimension.get("penalties") or {}).values(), magnitude=True) > 0:
                    penalized_dimensions += 1
                finding = analyze_dimension(dimension)
                if finding is None:
                    continue

                current_public = _finite_number(product.get("quality_score_v4_100"))
                alternative_public = _alternative_public_score(
                    product, str(dimension_name), finding
                )
                current_tier = product.get("quality_tier")
                alternative_tier = (
                    _quality_tier(alternative_public)
                    if alternative_public is not None
                    else None
                )
                current_raw = _finite_number(product.get("raw_score_v4_100"))
                alternative_raw = (
                    _round(current_raw - finding["absorbed_amount"])
                    if current_raw is not None
                    else None
                )

                findings.append(
                    {
                        "dsld_id": product.get("dsld_id"),
                        "brand_name": product.get("brand_name"),
                        "product_name": product.get("product_name"),
                        "module": module_breakdown.get("module"),
                        "dimension": str(dimension_name),
                        **finding,
                        "current_raw_score": current_raw,
                        "alternative_raw_score": alternative_raw,
                        "current_final_score": current_public,
                        "alternative_final_score": alternative_public,
                        "public_score_delta": (
                            _round(alternative_public - current_public)
                            if alternative_public is not None and current_public is not None
                            else None
                        ),
                        "current_tier": current_tier,
                        "alternative_tier": alternative_tier,
                        "tier_movement": (
                            "none"
                            if current_tier == alternative_tier
                            else f"{current_tier} -> {alternative_tier}"
                        ),
                        "source_file": path.as_posix(),
                    }
                )

    findings.sort(
        key=lambda row: (
            str(row.get("penalty_policy_class")),
            str(row.get("module")),
            str(row.get("brand_name")),
            str(row.get("product_name")),
            str(row.get("dsld_id")),
        )
    )
    by_module = Counter(str(row["module"]) for row in findings)
    by_policy = Counter(str(row["penalty_policy_class"]) for row in findings)
    by_tier = Counter(str(row["tier_movement"]) for row in findings)
    total_absorbed = _round(sum(row["absorbed_amount"] for row in findings))
    total_public_delta = _round(
        sum(row["public_score_delta"] or 0.0 for row in findings)
    )

    return {
        "_metadata": {
            "report": "v4_absorbed_penalty_policy_audit",
            "schema_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input_file_count": len(paths),
            "input_fingerprint_sha256": _input_fingerprint(paths),
            "scoring_behavior_changed": False,
        },
        "summary": {
            "products_scanned": products_scanned,
            "penalized_dimensions_scanned": penalized_dimensions,
            "affected_products": len(findings),
            "affected_dimensions": len(findings),
            "total_absorbed_raw_points": total_absorbed,
            "total_alternative_public_score_delta": total_public_delta,
            "by_module": dict(sorted(by_module.items())),
            "by_policy_class": dict(sorted(by_policy.items())),
            "tier_movements": dict(sorted(by_tier.items())),
            "recommended_policy": {
                "never_absorbable_material_defect": [
                    "B2_false_allergen_free_claim",
                    "b2_false_allergen_free_claim",
                ],
                "potentially_absorbable_soft_debt": [
                    "B5_proprietary_blend_opacity",
                    "b5_proprietary_blend_opacity",
                ],
                "decision": (
                    "Do not globally reverse penalty order. If policy changes, "
                    "subtract contradicted allergen-free claims after the cap; "
                    "retain current ordering for blend-opacity debt pending the "
                    "reviewer benchmark."
                ),
            },
        },
        "findings": findings,
    }


def _write_csv(report: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "dsld_id",
        "brand_name",
        "product_name",
        "module",
        "dimension",
        "gross_positive_credit",
        "dimension_cap",
        "positive_headroom",
        "penalties",
        "total_penalty_amount",
        "absorbed_amount",
        "current_dimension_score",
        "alternative_dimension_score",
        "penalty_policy_class",
        "absorption_attribution",
        "current_raw_score",
        "alternative_raw_score",
        "current_final_score",
        "alternative_final_score",
        "public_score_delta",
        "current_tier",
        "alternative_tier",
        "tier_movement",
        "source_file",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for finding in report["findings"]:
            row = copy.deepcopy(finding)
            row["penalties"] = json.dumps(
                row["penalties"], sort_keys=True, separators=(",", ":")
            )
            writer.writerow(row)


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    tier_movement_count = sum(
        count
        for movement, count in summary["tier_movements"].items()
        if movement != "none"
    )
    lines = [
        "# V4 absorbed-penalty policy audit",
        "",
        "This is an analysis artifact only. It does not change scoring.",
        "",
        "## Corpus result",
        "",
        f"- Products scanned: **{summary['products_scanned']:,}**",
        f"- Products with absorbed penalties: **{summary['affected_products']:,}**",
        f"- Raw penalty points absorbed: **{summary['total_absorbed_raw_points']:.4f}**",
        (
            "- Alternative public-score movement if every affected penalty moved "
            f"post-cap: **{summary['total_alternative_public_score_delta']:.1f}** points"
        ),
        f"- Products crossing a quality tier: **{tier_movement_count}**",
        "",
        "## Policy split",
        "",
        (
            f"- Material-defect population: "
            f"**{summary['by_policy_class'].get('contains_never_absorbable_material_defect', 0)}** "
            "products containing a contradicted allergen-free claim."
        ),
        (
            f"- Soft-debt-only population: "
            f"**{summary['by_policy_class'].get('potentially_absorbable_soft_debt', 0)}** "
            "products carrying proprietary-blend opacity."
        ),
        "",
        "Recommendation: do not globally reverse penalty ordering. A later policy "
        "change should move contradicted allergen-free claims after the cap while "
        "leaving blend-opacity ordering unchanged until the reviewer benchmark.",
        "",
        "The complete per-product table is in `affected_products.csv`; the exact "
        "machine-readable evidence and input fingerprint are in `report.json`.",
        "",
    ]
    if tier_movement_count:
        lines.extend(
            [
                "## Tier movements under the global alternative",
                "",
                *[
                    f"- {movement}: **{count}**"
                    for movement, count in summary["tier_movements"].items()
                    if movement != "none"
                ],
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scored-glob",
        default="scripts/products/output_*_scored/scored/scored_cleaned_batch_*.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("scripts/reports/v4_absorbed_penalty_audit"),
    )
    args = parser.parse_args()

    paths = [Path(path) for path in sorted(glob.glob(args.scored_glob))]
    if not paths:
        raise SystemExit(f"No scored artifacts matched {args.scored_glob!r}")

    report = build_report(paths)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(report, args.output_dir / "affected_products.csv")
    _write_markdown(report, args.output_dir / "README.md")

    summary = report["summary"]
    print(
        f"Scanned {summary['products_scanned']} products; "
        f"{summary['affected_products']} affected; "
        f"{summary['total_absorbed_raw_points']} raw points absorbed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
