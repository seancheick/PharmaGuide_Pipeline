#!/usr/bin/env python3
"""Create a human-reviewable v3 vs v4 side-by-side sample.

This is the operator-facing tuning artifact. The full-corpus delta CSV is
machine-oriented; this report selects a deterministic 100-product shipped
sample across modules and review buckets, then emits v3 sections and v4
dimensions side by side.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (str(SCRIPTS_ROOT), str(SCRIPTS_ROOT / "api_audit")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import v4_full_corpus_delta as delta  # noqa: E402
from v4_release_readiness_audit import classify_row  # noqa: E402


DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "v4_side_by_side_review"
DEFAULT_SAMPLE_SIZE = 100
MODULE_ORDER = ["generic", "multi_or_prenatal", "probiotic", "omega", "sports"]
SCORE_BANDS = (
    (95.0, "near_perfect", "95-100 near-perfect; requires maxed rubric quality with no meaningful penalties"),
    (90.0, "exceptional", "90-94 exceptional; rare on the raw rubric scale"),
    (80.0, "excellent", "80-89 excellent on the raw rubric scale"),
    (60.0, "good", "60-79 good / solid, not top-tier"),
    (40.0, "acceptable", "40-59 acceptable but quality debt remains"),
    (0.0, "weak", "<40 weak; POOR threshold"),
)


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def score_band(score: Any) -> str:
    value = _num(score)
    if value is None:
        return "not_scored"
    for threshold, band, _description in SCORE_BANDS:
        if value >= threshold:
            return band
    return "weak"


def _delta_abs(row: Dict[str, Any]) -> float:
    return abs(_num(row.get("raw_score_delta_vs_v3")) or 0.0)


def _row_sort_key(row: Dict[str, Any]) -> tuple:
    return (
        str(row.get("v4_module") or ""),
        str(row.get("primary_class") or ""),
        str(row.get("brand_name") or ""),
        str(row.get("product_name") or ""),
        str(row.get("dsld_id") or ""),
    )


def _add_unique(selected: List[Dict[str, Any]], seen: set[str], rows: Iterable[Dict[str, Any]], limit: int) -> None:
    for row in rows:
        if len(selected) >= limit:
            return
        dsld_id = str(row.get("dsld_id") or "")
        if not dsld_id or dsld_id in seen:
            continue
        selected.append(row)
        seen.add(dsld_id)


def _quotas(rows: List[Dict[str, Any]], sample_size: int) -> Dict[str, int]:
    counts = Counter(str(row.get("v4_module") or "unknown") for row in rows)
    quotas: Dict[str, int] = {}
    preferred_modules = [module for module in MODULE_ORDER if counts.get(module, 0)]
    if preferred_modules:
        base = sample_size // len(preferred_modules)
        remaining = sample_size
        for module in preferred_modules:
            quota = min(counts[module], base)
            quotas[module] = quota
            remaining -= quota
        while remaining > 0:
            grew = False
            for module in preferred_modules:
                if remaining <= 0:
                    break
                if quotas[module] < counts[module]:
                    quotas[module] += 1
                    remaining -= 1
                    grew = True
            if not grew:
                break
        return quotas

    remaining = sample_size
    for module in MODULE_ORDER:
        if counts.get(module, 0):
            quota = min(counts[module], max(8, round(sample_size * counts[module] / max(len(rows), 1))))
            quotas[module] = quota
            remaining -= quota
    other_modules = sorted(m for m in counts if m not in quotas)
    for module in other_modules:
        if remaining <= 0:
            break
        quota = min(counts[module], max(1, round(sample_size * counts[module] / max(len(rows), 1))))
        quotas[module] = quota
        remaining -= quota
    while remaining > 0:
        grew = False
        for module in sorted(quotas):
            if remaining <= 0:
                break
            if quotas[module] < counts[module]:
                quotas[module] += 1
                remaining -= 1
                grew = True
        if not grew:
            break
    while sum(quotas.values()) > sample_size:
        module = max(quotas, key=lambda m: quotas[m])
        quotas[module] -= 1
    return quotas


def select_review_sample(rows: List[Dict[str, Any]], sample_size: int = DEFAULT_SAMPLE_SIZE) -> List[Dict[str, Any]]:
    """Select a deterministic, category-balanced review sample."""
    candidates = [
        row for row in rows
        if row.get("in_shipped_universe")
        and row.get("v3_shipped_score") is not None
        and row.get("v4_score") is not None
    ]
    for row in candidates:
        row["release_classification"] = classify_row(row)
    by_module: Dict[str, List[Dict[str, Any]]] = {}
    for row in candidates:
        by_module.setdefault(str(row.get("v4_module") or "unknown"), []).append(row)

    selected: List[Dict[str, Any]] = []
    seen: set[str] = set()
    quotas = _quotas(candidates, sample_size)

    for module, quota in sorted(quotas.items()):
        module_rows = by_module.get(module, [])
        module_selected: List[Dict[str, Any]] = []
        module_seen: set[str] = set()

        review_rows = sorted(
            [row for row in module_rows if str(row.get("release_classification", "")).startswith("REVIEW_")],
            key=lambda r: (-_delta_abs(r), _row_sort_key(r)),
        )
        _add_unique(module_selected, module_seen, review_rows, max(1, round(quota * 0.30)))

        soft_cap_rows = sorted(
            [row for row in module_rows if row.get("v4_completeness_soft_missing")],
            key=lambda r: (-_delta_abs(r), _row_sort_key(r)),
        )
        _add_unique(module_selected, module_seen, soft_cap_rows, max(len(module_selected), round(quota * 0.55)))

        high_score_rows = sorted(
            [row for row in module_rows if (_num(row.get("v4_score")) or 0.0) >= 85.0],
            key=lambda r: (-(r.get("v4_score") or 0.0), _row_sort_key(r)),
        )
        _add_unique(module_selected, module_seen, high_score_rows, max(len(module_selected), round(quota * 0.70)))

        largest_delta_rows = sorted(module_rows, key=lambda r: (-_delta_abs(r), _row_sort_key(r)))
        _add_unique(module_selected, module_seen, largest_delta_rows, max(len(module_selected), round(quota * 0.90)))

        balanced_rows = sorted(module_rows, key=_row_sort_key)
        _add_unique(module_selected, module_seen, balanced_rows, quota)

        _add_unique(selected, seen, module_selected, sample_size)

    if len(selected) < sample_size:
        fill = sorted(candidates, key=lambda r: (-_delta_abs(r), _row_sort_key(r)))
        _add_unique(selected, seen, fill, sample_size)

    return selected[:sample_size]


def _num_or_none(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta_reason(flat: Dict[str, Any]) -> str:
    """Mechanical, non-judgmental summary of the v3->v4 delta drivers. Names the
    likely contributors (low dimensions, removed trust, penalties, caps); the
    'is this legit?' call is left to the human reviewing the surface."""
    parts: List[str] = []
    sd = _num_or_none(flat.get("score_delta_v4_minus_v3"))
    if sd is None:
        parts.append("v4 not scored")
    elif sd >= 3:
        parts.append(f"v4 +{sd:.0f}")
    elif sd <= -3:
        parts.append(f"v4 {sd:.0f}")
    else:
        parts.append("~flat")
    ev = _num_or_none(flat.get("v4_evidence"))
    if ev is not None and ev <= 6:
        parts.append(f"evid {ev:.0f}/20")
    dose = _num_or_none(flat.get("v4_dose"))
    if dose is not None and dose <= 10:
        parts.append(f"dose {dose:.0f}/25")
    if (_num_or_none(flat.get("v4_verification_bonus")) or 0) == 0:
        parts.append("no verif bonus")
    if (_num_or_none(flat.get("v4_manufacturer_violations")) or 0) < 0:
        parts.append("mfr violation")
    if flat.get("v4_score_cap") not in (None, ""):
        parts.append(f"cap {flat.get('v4_score_cap')}")
    if flat.get("v4_verdict_ceiling") not in (None, ""):
        parts.append(f"ceiling {flat.get('v4_verdict_ceiling')}")
    if flat.get("v4_completeness_missing"):
        parts.append("missing:" + flat["v4_completeness_missing"])
    return "; ".join(parts)


def flatten_row(row: Dict[str, Any]) -> Dict[str, Any]:
    v3_sections = row.get("v3_sections") or {}
    v4_dimensions = row.get("v4_dimensions") or {}
    flat = {
        "dsld_id": row.get("dsld_id"),
        "brand_name": row.get("brand_name"),
        "product_name": row.get("product_name"),
        "primary_class": row.get("primary_class"),
        "v4_module": row.get("v4_module"),
        "release_classification": row.get("release_classification"),
        "v3_score": row.get("v3_shipped_score"),
        "v3_verdict": row.get("v3_verdict"),
        "v3_safety_verdict": row.get("v3_safety_verdict"),
        "v3_A_ingredient_quality": v3_sections.get("A"),
        "v3_B_safety_purity": v3_sections.get("B"),
        "v3_C_evidence_research": v3_sections.get("C"),
        "v3_D_brand_trust": v3_sections.get("D"),
        "v3_E_dose_bonus": v3_sections.get("E"),
        "v3_B_bonuses": v3_sections.get("B_bonuses"),
        "v3_B_penalties": v3_sections.get("B_penalties"),
        "v4_raw_score": row.get("v4_raw_score"),
        "v4_score": row.get("v4_score"),
        "v4_score_band": score_band(row.get("v4_score")),
        "v4_verdict": row.get("v4_verdict"),
        "v4_confidence": (row.get("v4_confidence_detail") or {}).get("band"),
        "raw_delta_v4_minus_v3": row.get("raw_score_delta_vs_v3"),
        "score_delta_v4_minus_v3": row.get("score_delta_vs_v3"),
        "v4_formulation": v4_dimensions.get("formulation"),
        "v4_dose": v4_dimensions.get("dose"),
        "v4_evidence": v4_dimensions.get("evidence"),
        "v4_transparency": v4_dimensions.get("transparency"),
        # Phase 4: trust is now an additive verification bonus (0-8), not a
        # core dimension; v4_verification_trust_0_15 is the pre-rescale score.
        "v4_verification_bonus": row.get("v4_verification_bonus"),
        "v4_verification_trust_0_15": row.get("v4_verification_trust_0_15"),
        "v4_manufacturer_bonus": row.get("v4_manufacturer_bonus"),
        # safety_hygiene lives outside the `dimensions` dict — read it from the
        # row the delta tool now surfaces (was always null via v4_dimensions).
        "v4_safety_hygiene_base": row.get("v4_safety_hygiene"),
        "v4_manufacturer_violations": row.get("v4_manufacturer_violations"),
        "v4_completeness_missing": "|".join(row.get("v4_completeness_missing") or []),
        "v4_completeness_soft_missing": "|".join(row.get("v4_completeness_soft_missing") or []),
        "v4_score_cap": row.get("v4_completeness_score_cap"),
        "v4_verdict_ceiling": row.get("v4_completeness_verdict_ceiling"),
        "compression_flags": "|".join(row.get("compression_flags") or []),
        "v3_sections_json": _json(v3_sections),
        "v4_dimensions_json": _json(v4_dimensions),
        "v4_dimension_metadata_json": _json(row.get("v4_dimension_metadata")),
    }
    flat["delta_reason"] = _delta_reason(flat)
    return flat


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flat = [flatten_row(row) for row in rows]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(flat[0].keys()) if flat else [])
        writer.writeheader()
        writer.writerows(flat)


def write_json(rows: List[Dict[str, Any]], path: Path) -> None:
    path.write_text(json.dumps([flatten_row(row) for row in rows], indent=2, ensure_ascii=False) + "\n")


def write_markdown(rows: List[Dict[str, Any]], path: Path, summary: Dict[str, Any]) -> None:
    lines = [
        "# v3 vs v4 Side-by-Side Review Sample",
        "",
        f"- Generated: {summary['generated']}",
        f"- Sample size: {summary['sample_size']}",
        f"- Source universe: shipped products with both v3 and v4 scores",
        f"- Raw delta = v4 raw rubric score minus shipped v3 score",
        f"- Score delta = v4 production score minus shipped v3 score",
        f"- v4 production score policy: score_100 is the raw rubric score, not a stretched display value",
        "",
        "## Distribution",
        "",
        f"- By v4 module: `{summary['module_counts']}`",
        f"- By review classification: `{summary['classification_counts']}`",
        f"- By v4 score band: `{summary['score_band_counts']}`",
        f"- Mean raw delta: `{summary['mean_raw_delta']}`",
        f"- Mean score delta: `{summary['mean_score_delta']}`",
        "",
        "## v4 Raw-Score Bands",
        "",
        *(f"- `{band}`: {description}" for _threshold, band, description in SCORE_BANDS),
        "",
        "## Products",
        "",
        "| # | dsld | product | class/module | v3 | v4 score | band | deltas | verdicts | v4 dims | flags/debt |",
        "|---:|---|---|---|---:|---:|---|---|---|---|---|",
    ]
    for idx, row in enumerate(rows, 1):
        flat = flatten_row(row)
        dims = (
            f"F {flat['v4_formulation']}; D {flat['v4_dose']}; "
            f"E {flat['v4_evidence']}; T {flat['v4_transparency']}; "
            f"VB {flat['v4_verification_bonus']}; "
            f"Trust15 {flat['v4_verification_trust_0_15']}; "
            f"Hyg {flat['v4_safety_hygiene_base']}"
        )
        debt = "; ".join(
            part for part in [
                flat["release_classification"],
                flat["v4_completeness_soft_missing"],
                flat["compression_flags"],
            ]
            if part
        )
        product = f"{flat['brand_name']} — {flat['product_name']}"
        lines.append(
            f"| {idx} | {flat['dsld_id']} | {product[:72]} | "
            f"{flat['primary_class']} / {flat['v4_module']} | "
            f"{flat['v3_score']} | {flat['v4_score']} | {flat['v4_score_band']} | "
            f"raw {flat['raw_delta_v4_minus_v3']}; score {flat['score_delta_v4_minus_v3']} | "
            f"{flat['v3_verdict']}→{flat['v4_verdict']} | {dims} | {debt} |"
        )
    path.write_text("\n".join(lines) + "\n")


def build_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    raw_deltas = [_num(row.get("raw_score_delta_vs_v3")) or 0.0 for row in rows]
    score_deltas = [_num(row.get("score_delta_vs_v3")) or 0.0 for row in rows]
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(rows),
        "module_counts": dict(Counter(str(row.get("v4_module") or "unknown") for row in rows).most_common()),
        "primary_class_counts": dict(Counter(str(row.get("primary_class") or "unknown") for row in rows).most_common()),
        "classification_counts": dict(Counter(str(row.get("release_classification") or "") for row in rows).most_common()),
        "score_band_counts": dict(Counter(score_band(row.get("v4_score")) for row in rows).most_common()),
        "mean_raw_delta": round(sum(raw_deltas) / len(raw_deltas), 2) if rows else None,
        "mean_score_delta": round(sum(score_deltas) / len(score_deltas), 2) if rows else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-root", type=Path, default=delta.DEFAULT_PRODUCTS_ROOT)
    parser.add_argument("--dist-db", type=Path, default=delta.DEFAULT_DIST_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    args = parser.parse_args()

    enriched_index = delta.canary.build_enriched_index(args.products_root)
    scored_index = delta.canary.build_scored_index(args.products_root)
    shipped_universe = delta.load_shipped_universe(args.dist_db)
    rows = delta.build_rows(enriched_index, scored_index)
    for row in rows:
        row["in_shipped_universe"] = (
            (not shipped_universe) or (row.get("dsld_id") in shipped_universe)
        )

    sample = select_review_sample(rows, sample_size=args.sample_size)
    summary = build_summary(sample)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(sample, args.out_dir / "v3_v4_side_by_side_100.csv")
    write_json(sample, args.out_dir / "v3_v4_side_by_side_100.json")
    write_markdown(sample, args.out_dir / "v3_v4_side_by_side_100.md", summary)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))
    print(f"Wrote {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
