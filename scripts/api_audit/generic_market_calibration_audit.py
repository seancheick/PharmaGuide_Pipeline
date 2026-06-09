#!/usr/bin/env python3
"""Read-only v4 generic-market calibration audit.

This report answers the calibration question before changing weights:

* Are credible generic-route products clustering too low?
* Which dimensions are binding: formulation, dose, evidence, transparency,
  verification, manufacturer trust, or penalties?
* Do market cohorts (magnesium, creatine, berberine, D3/K2, etc.) line up with
  the expected quality bands?

The tool does not mutate products or scores.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for _p in (str(SCRIPTS_ROOT), str(SCRIPTS_ROOT / "api_audit")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from score_supplements_v4 import score_product_v4  # noqa: E402
from scoring_v4.modules.generic_helpers import get_active_ingredients  # noqa: E402
import v4_canary_report as canary  # noqa: E402


DEFAULT_PRODUCTS_ROOT = SCRIPTS_ROOT / "products"
DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "v4_generic_market_calibration"

QUALITY_BANDS = (
    ("Excellent", 85.0, 100.0),
    ("Good", 70.0, 85.0),
    ("Fair", 50.0, 70.0),
    ("Poor", 0.0, 50.0),
)

CORE_CAPS = {
    "formulation": 30.0,
    "dose": 25.0,
    "evidence": 20.0,
    "transparency": 10.0,
}

PREMIUM_BRANDS = {
    "thorne",
    "pure encapsulations",
    "designs for health",
    "nordic naturals",
    "metagenics",
    "seeking health",
    "xymogen",
    "orthomolecular",
    "ortho molecular",
    "integrative therapeutics",
    "klaire labs",
}

GOOD_BRANDS = {
    "now",
    "now foods",
    "life extension",
    "jarrow",
    "jarrow formulas",
    "doctor's best",
    "doctors best",
    "sports research",
    "solgar",
    "garden of life",
    "carlson",
}

AVERAGE_BRANDS = {
    "nature made",
    "spring valley",
    "cvs health",
    "nature's bounty",
    "natures bounty",
    "vitafusion",
    "gnc",
    "swanson",
}

COHORT_DEFINITIONS = {
    "magnesium": ("magnesium",),
    "creatine": ("creatine",),
    "berberine": ("berberine",),
    "d3_k2": ("vitamin d", "vitamin k", "d3", "k2", "menaquinone"),
    "coq10": ("coq10", "coenzyme q10", "ubiquinol", "ubiquinone"),
    "nac": ("nac", "n-acetyl", "acetylcysteine"),
    "ashwagandha": ("ashwagandha", "withania", "ksm-66", "sensoril"),
    "curcumin": ("curcumin", "turmeric", "meriva", "bcm-95"),
    "zinc": ("zinc",),
    "melatonin": ("melatonin",),
}


def _num(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _quality_band(score: Optional[float]) -> str:
    if score is None:
        return "Not Scored"
    for label, lo, hi in QUALITY_BANDS:
        if lo <= score < hi or (label == "Excellent" and score >= lo):
            return label
    return "Poor"


def _brand_tier(brand: Any) -> str:
    b = _norm(brand)
    if not b:
        return "unknown"
    if any(name in b for name in PREMIUM_BRANDS):
        return "premium"
    if any(name in b for name in GOOD_BRANDS):
        return "good"
    if any(name in b for name in AVERAGE_BRANDS):
        return "average"
    return "unclassified"


def _ingredient_text(product: Dict[str, Any]) -> str:
    parts: List[str] = [
        str(product.get("product_name") or product.get("fullName") or ""),
        str(product.get("brand_name") or product.get("brandName") or ""),
    ]
    for row in get_active_ingredients(product):
        if not isinstance(row, dict):
            continue
        for key in ("canonical_id", "standard_name", "name", "ingredient_name", "form"):
            value = row.get(key)
            if value:
                parts.append(str(value))
    return " ".join(parts).lower()


def _cohorts_for(product: Dict[str, Any]) -> List[str]:
    text = _ingredient_text(product)
    cohorts: List[str] = []
    for cohort, needles in COHORT_DEFINITIONS.items():
        if any(needle in text for needle in needles):
            cohorts.append(cohort)
    return cohorts or ["other_generic"]


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dimension_payload(module: Dict[str, Any], name: str) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(module.get("dimensions")).get(name))


def _dimension_score(module: Dict[str, Any], name: str) -> Optional[float]:
    return _num(_dimension_payload(module, name).get("score"))


def _penalty_total(module: Dict[str, Any]) -> float:
    total = 0.0
    for payload in _safe_dict(module.get("dimensions")).values():
        for value in _safe_dict(_safe_dict(payload).get("penalties")).values():
            n = _num(value)
            if n is not None:
                total += abs(n)
    mv = _num(_safe_dict(module.get("manufacturer_violations")).get("score"))
    if mv is not None and mv < 0:
        total += abs(mv)
    return round(total, 4)


def _why_not_higher(module: Dict[str, Any], score: Optional[float], confidence: str) -> List[str]:
    if score is None:
        return ["not_scored"]

    reasons: List[str] = []
    for dim, cap in CORE_CAPS.items():
        value = _dimension_score(module, dim)
        if value is None:
            reasons.append(f"{dim}: missing")
            continue
        headroom = cap - value
        if headroom >= 8:
            reasons.append(f"{dim}: large headroom ({value:.1f}/{cap:.0f})")
        elif headroom >= 5:
            reasons.append(f"{dim}: moderate headroom ({value:.1f}/{cap:.0f})")

    verification = _num(_safe_dict(module.get("verification_bonus")).get("score")) or 0.0
    if verification < 2.0:
        reasons.append(f"verification: low bonus ({verification:.1f}/8)")

    manufacturer = _num(_safe_dict(module.get("manufacturer_trust")).get("score")) or 0.0
    if manufacturer < 2.0:
        reasons.append(f"manufacturer trust: low ({manufacturer:.1f}/5)")

    penalties = _penalty_total(module)
    if penalties >= 5.0:
        reasons.append(f"penalties: {penalties:.1f} pts")

    if confidence and confidence.lower() not in {"high", "very_high"}:
        reasons.append(f"confidence: {confidence}")

    return reasons[:6] or ["score reflects balanced rubric; no single binding gap"]


def _expected_band(brand_tier: str, cohorts: List[str]) -> str:
    """Heuristic market expectation used for review, not scoring."""
    if brand_tier == "premium":
        return "Good-Excellent"
    if brand_tier == "good":
        return "Good"
    if brand_tier == "average":
        return "Fair-Good"
    if any(c in {"creatine", "magnesium", "coq10", "d3_k2"} for c in cohorts):
        return "Fair-Good"
    return "Unknown"


def build_rows(products: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for product in products:
        shadow = score_product_v4(product)
        module_name = str(shadow.get("v4_module") or "")
        if module_name != "generic":
            continue

        breakdown = _safe_dict(shadow.get("v4_breakdown"))
        module = _safe_dict(breakdown.get("module"))
        confidence = str(shadow.get("v4_confidence") or "")
        score = _num(shadow.get("raw_score_v4_100"))
        cohorts = _cohorts_for(product)
        brand_tier = _brand_tier(product.get("brand_name") or product.get("brandName"))

        row = {
            "dsld_id": canary._dsld_id(product),
            "brand_name": product.get("brand_name") or product.get("brandName"),
            "product_name": product.get("product_name") or product.get("fullName"),
            "score": score,
            "quality_band": _quality_band(score),
            "safety_verdict": shadow.get("v4_verdict"),
            "confidence": confidence,
            "brand_tier": brand_tier,
            "expected_market_band": _expected_band(brand_tier, cohorts),
            "cohorts": cohorts,
            "formulation": _dimension_score(module, "formulation"),
            "dose": _dimension_score(module, "dose"),
            "evidence": _dimension_score(module, "evidence"),
            "transparency": _dimension_score(module, "transparency"),
            "verification_bonus": _num(_safe_dict(module.get("verification_bonus")).get("score")),
            "manufacturer_trust": _num(_safe_dict(module.get("manufacturer_trust")).get("score")),
            "manufacturer_violations": _num(_safe_dict(module.get("manufacturer_violations")).get("score")),
            "safety_hygiene": _num(_safe_dict(module.get("safety_hygiene_base")).get("score")),
            "penalty_total": _penalty_total(module),
            "why_not_higher": _why_not_higher(module, score, confidence),
        }
        rows.append(row)
    return rows


def _stats(values: List[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"count": 0, "mean": None, "p50": None, "min": None, "max": None}
    values = sorted(values)
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 2),
        "p50": round(statistics.median(values), 2),
        "min": round(values[0], 2),
        "max": round(values[-1], 2),
    }


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    scored = [r for r in rows if r.get("score") is not None]
    by_band = Counter(r["quality_band"] for r in scored)
    by_brand_tier = Counter(r["brand_tier"] for r in scored)
    by_cohort: Dict[str, List[float]] = defaultdict(list)
    for row in scored:
        score = _num(row.get("score"))
        if score is None:
            continue
        for cohort in row.get("cohorts") or []:
            by_cohort[cohort].append(score)

    premium = [r for r in scored if r.get("brand_tier") == "premium"]
    good = [r for r in scored if r.get("brand_tier") == "good"]
    avg = [r for r in scored if r.get("brand_tier") == "average"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generic_rows": len(rows),
        "scored_rows": len(scored),
        "score_stats": _stats([r["score"] for r in scored if r.get("score") is not None]),
        "quality_band_counts": dict(by_band.most_common()),
        "brand_tier_counts": dict(by_brand_tier.most_common()),
        "brand_tier_stats": {
            "premium": _stats([r["score"] for r in premium if r.get("score") is not None]),
            "good": _stats([r["score"] for r in good if r.get("score") is not None]),
            "average": _stats([r["score"] for r in avg if r.get("score") is not None]),
        },
        "dimension_stats": {
            key: _stats([r[key] for r in scored if r.get(key) is not None])
            for key in (
                "formulation",
                "dose",
                "evidence",
                "transparency",
                "verification_bonus",
                "manufacturer_trust",
                "safety_hygiene",
            )
        },
        "cohort_stats": {
            cohort: _stats(scores)
            for cohort, scores in sorted(by_cohort.items())
        },
        "top_scores": [
            _summary_row(r)
            for r in sorted(scored, key=lambda x: x.get("score") or -1, reverse=True)[:25]
        ],
        "bottom_scores": [
            _summary_row(r)
            for r in sorted(scored, key=lambda x: x.get("score") or 101)[:25]
        ],
        "premium_under_70": [
            _summary_row(r)
            for r in sorted(
                [r for r in premium if (r.get("score") or 0) < 70],
                key=lambda x: x.get("score") or 0,
            )[:50]
        ],
    }


def _summary_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dsld_id": row.get("dsld_id"),
        "brand_name": row.get("brand_name"),
        "product_name": row.get("product_name"),
        "score": row.get("score"),
        "quality_band": row.get("quality_band"),
        "brand_tier": row.get("brand_tier"),
        "cohorts": row.get("cohorts"),
        "why_not_higher": row.get("why_not_higher"),
    }


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "dsld_id", "brand_name", "product_name", "score", "quality_band",
        "safety_verdict", "confidence", "brand_tier", "expected_market_band",
        "cohorts", "formulation", "dose", "evidence", "transparency",
        "verification_bonus", "manufacturer_trust", "manufacturer_violations",
        "safety_hygiene", "penalty_total", "why_not_higher",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            item = dict(row)
            item["cohorts"] = ";".join(row.get("cohorts") or [])
            item["why_not_higher"] = "; ".join(row.get("why_not_higher") or [])
            writer.writerow({col: item.get(col) for col in cols})


def write_markdown(summary: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# v4 Generic Market Calibration Audit",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "## Headline",
        "",
        f"- Generic-route rows: `{summary['generic_rows']}`",
        f"- Scored rows: `{summary['scored_rows']}`",
        f"- Score stats: `{summary['score_stats']}`",
        f"- Quality bands: `{summary['quality_band_counts']}`",
        "",
        "## Brand Tier Stats",
        "",
        "| Tier | Count | Mean | P50 | Min | Max |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for tier, stats in summary["brand_tier_stats"].items():
        lines.append(
            f"| {tier} | {stats['count']} | {stats['mean']} | {stats['p50']} | "
            f"{stats['min']} | {stats['max']} |"
        )
    lines.extend([
        "",
        "## Dimension Stats",
        "",
        "| Dimension | Count | Mean | P50 | Min | Max |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for dim, stats in summary["dimension_stats"].items():
        lines.append(
            f"| {dim} | {stats['count']} | {stats['mean']} | {stats['p50']} | "
            f"{stats['min']} | {stats['max']} |"
        )
    lines.extend([
        "",
        "## Cohort Stats",
        "",
        "| Cohort | Count | Mean | P50 | Min | Max |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for cohort, stats in summary["cohort_stats"].items():
        lines.append(
            f"| {cohort} | {stats['count']} | {stats['mean']} | {stats['p50']} | "
            f"{stats['min']} | {stats['max']} |"
        )
    lines.extend(["", "## Top 25 Generic Scores", ""])
    lines.extend(_table_rows(summary["top_scores"]))
    lines.extend(["", "## Bottom 25 Generic Scores", ""])
    lines.extend(_table_rows(summary["bottom_scores"]))
    lines.extend(["", "## Premium-Tier Products Under 70", ""])
    lines.extend(_table_rows(summary["premium_under_70"]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _table_rows(rows: List[Dict[str, Any]]) -> List[str]:
    if not rows:
        return ["_None._"]
    lines = [
        "| id | brand | product | score | band | why not higher |",
        "|---|---|---|---:|---|---|",
    ]
    for row in rows:
        why = "; ".join(row.get("why_not_higher") or [])
        lines.append(
            f"| {row.get('dsld_id')} | {_md(row.get('brand_name'))} | "
            f"{_md(row.get('product_name'))} | {row.get('score')} | "
            f"{row.get('quality_band')} | {_md(why)} |"
        )
    return lines


def _md(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products-root", type=Path, default=DEFAULT_PRODUCTS_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=None, help="Optional product limit for fast local probes")
    args = parser.parse_args()

    enriched_index = canary.build_enriched_index(args.products_root)
    products = list(enriched_index.values())
    if args.limit:
        products = products[: args.limit]

    rows = build_rows(products)
    summary = summarize(rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(rows, args.out_dir / "generic_market_calibration.csv")
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_markdown(summary, args.out_dir / "generic_market_calibration.md")

    print(f"Wrote {len(rows)} generic rows to {args.out_dir}")
    print(f"Quality bands: {summary['quality_band_counts']}")
    print(f"Score stats: {summary['score_stats']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
