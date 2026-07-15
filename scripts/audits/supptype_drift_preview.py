#!/usr/bin/env python3
"""TEMPORARY migration harness — supplement-type consolidation drift preview.

READ-ONLY. It never chooses a shipped result and never writes pipeline output.
DELETE THIS FILE at cutover acceptance (consolidation Phase 5).

WHY THIS EXISTS
    A full pipeline run costs ~1 hour and the release gates are sequential and
    fail-closed, so a classifier change is discovered one layer at a time. The
    supp-type consolidation re-routes a large slice of the catalog (~3% genuine
    misroutes plus a 31% `general_supplement` catch-all), so iterating against
    the pipeline would mean many hour-long rounds.

    This harness answers, in minutes and off the pipeline:
      * which products change primary_type, and why
      * the old -> new confusion matrix
      * which SCORES move, and — the part that actually matters — which
        grades/verdicts FLIP
      * which of the frozen scoring-snapshot fixtures will drift

USAGE
    source scripts/python_env.sh
    $PG_PYTHON scripts/audits/supptype_drift_preview.py baseline
    # ... edit classify_supplement / consumers ...
    $PG_PYTHON scripts/audits/supptype_drift_preview.py compare --score

    `baseline` recomputes with the CURRENT code and stores it, so the diff is
    always code-vs-code rather than code-vs-stale-blob.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from supplement_taxonomy import classify_supplement  # noqa: E402

PRODUCTS_DIR = SCRIPTS_DIR / "products"
FIXTURES_DIR = SCRIPTS_DIR / "tests" / "fixtures" / "contract_snapshots"
DEFAULT_BASELINE = SCRIPTS_DIR / "products" / "reports" / "supptype_baseline.json"

# Taxonomy types that mean "one scorable active". Kept here (not imported) on
# purpose: the harness must observe the code, not share its assumptions.
SINGLE_FAMILY = {"single_vitamin", "single_mineral", "amino_acid"}


def iter_enriched() -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Yield (brand, product) for every enriched product on disk."""
    for brand_dir in sorted(PRODUCTS_DIR.glob("output_*_enriched")):
        brand = brand_dir.name[len("output_"):-len("_enriched")]
        for path in sorted((brand_dir / "enriched").glob("*.json")):
            try:
                payload = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                print(f"  ! unreadable {path.name}: {exc}", file=sys.stderr)
                continue
            for product in (payload if isinstance(payload, list) else [payload]):
                if isinstance(product, dict) and product.get("dsld_id") is not None:
                    yield brand, product


def classify_row(product: Dict[str, Any]) -> Dict[str, Any]:
    """Run the CURRENT classifier and capture what drives routing."""
    taxo = classify_supplement(product) or {}
    return {
        "primary_type": taxo.get("primary_type") or "",
        "confidence": taxo.get("classification_confidence"),
        "active_count": taxo.get("quantified_active_count"),
        "reasons": taxo.get("classification_reasons") or [],
    }


def build_snapshot() -> Dict[str, Any]:
    rows: Dict[str, Any] = {}
    for brand, product in iter_enriched():
        pid = str(product["dsld_id"])
        row = classify_row(product)
        row["brand"] = brand
        row["name"] = (product.get("product_name") or product.get("fullName") or "")[:70]
        rows[pid] = row
    return rows


def score_products(pids: set[str]) -> Dict[str, Any]:
    """Re-score ONLY the given products in-process (no pipeline)."""
    from score_supplements import SupplementScorer  # noqa: E402

    scorer = SupplementScorer()
    out: Dict[str, Any] = {}
    for _brand, product in iter_enriched():
        pid = str(product["dsld_id"])
        if pid not in pids:
            continue
        try:
            scored = scorer.score_product(product) or {}
        except Exception as exc:  # harness must never mask a real crash silently
            out[pid] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        out[pid] = {
            "score_100": scored.get("score_100_equivalent"),
            "grade": scored.get("grade"),
            "verdict": scored.get("verdict"),
        }
    return out


def frozen_fixture_ids() -> set[str]:
    if not FIXTURES_DIR.exists():
        return set()
    return {p.stem for p in FIXTURES_DIR.glob("*.json") if not p.stem.startswith("_")}


def cmd_baseline(args: argparse.Namespace) -> int:
    print("Classifying full enriched corpus with CURRENT code...")
    rows = build_snapshot()
    payload: Dict[str, Any] = {"types": rows}
    if args.score:
        print(f"Scoring all {len(rows)} products in-process (slow)...")
        payload["scores"] = score_products(set(rows))
    args.baseline.parent.mkdir(parents=True, exist_ok=True)
    args.baseline.write_text(json.dumps(payload))
    print(f"Baseline written: {args.baseline}  ({len(rows)} products)")
    dist = Counter(r["primary_type"] for r in rows.values())
    print("\nprimary_type distribution:")
    for t, n in dist.most_common():
        print(f"  {n:6d}  {n/len(rows)*100:5.1f}%  {t or '(empty)'}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    if not args.baseline.exists():
        print(f"No baseline at {args.baseline}. Run `baseline` first.", file=sys.stderr)
        return 2
    base = json.loads(args.baseline.read_text())
    base_types = base["types"]

    print("Re-classifying with current code...")
    new_types = build_snapshot()

    changed = {
        pid: (base_types[pid], new_types[pid])
        for pid in new_types
        if pid in base_types
        and base_types[pid]["primary_type"] != new_types[pid]["primary_type"]
    }
    total = len(new_types)
    print(f"\n{'='*66}\nTYPE DRIFT: {len(changed)}/{total} products "
          f"({len(changed)/total*100:.2f}%)\n{'='*66}")

    matrix = Counter((o["primary_type"], n["primary_type"]) for o, n in changed.values())
    print("\nconfusion matrix (old -> new, top 25):")
    for (old, new), n in matrix.most_common(25):
        print(f"  {n:6d}  {old or '(empty)':24s} -> {new or '(empty)'}")

    # Single-ness flips drive the formulation gates — call them out separately.
    flips = [
        pid for pid, (o, n) in changed.items()
        if (o["primary_type"] in SINGLE_FAMILY) != (n["primary_type"] in SINGLE_FAMILY)
    ]
    print(f"\nsingle-vs-multi flips (drive formulation floors/A6): {len(flips)}")

    fixtures = frozen_fixture_ids()
    fixture_hits = sorted(fixtures & set(changed))
    print(f"\nfrozen fixtures that will drift: {len(fixture_hits)}/{len(fixtures)}")
    for pid in fixture_hits:
        o, n = changed[pid]
        print(f"  {pid}  {o['primary_type']} -> {n['primary_type']}  ({n['brand']}: {n['name']})")

    if args.score:
        base_scores = base.get("scores") or {}
        if not base_scores:
            print("\n! baseline has no scores; re-run `baseline --score` to enable score diffing.",
                  file=sys.stderr)
            return 1
        print(f"\nRe-scoring {len(changed)} type-changed products in-process...")
        new_scores = score_products(set(changed))
        grade_flips, verdict_flips, errors = [], [], []
        for pid in changed:
            b, a = base_scores.get(pid, {}), new_scores.get(pid, {})
            if a.get("error"):
                errors.append((pid, a["error"]))
                continue
            if b.get("verdict") != a.get("verdict"):
                verdict_flips.append((pid, b.get("verdict"), a.get("verdict")))
            if b.get("grade") != a.get("grade"):
                grade_flips.append((pid, b.get("grade"), a.get("grade")))
        print(f"\n{'='*66}\nSCORE IMPACT (type-changed products only)\n{'='*66}")
        print(f"  verdict flips: {len(verdict_flips)}   <-- safety-critical, review each")
        for pid, b, a in verdict_flips[:20]:
            print(f"     {pid}: {b} -> {a}  ({changed[pid][1]['name']})")
        print(f"  grade flips:   {len(grade_flips)}")
        for pid, b, a in grade_flips[:10]:
            print(f"     {pid}: {b} -> {a}")
        if errors:
            print(f"  scoring errors: {len(errors)}")
            for pid, e in errors[:5]:
                print(f"     {pid}: {e}")

    if args.json_out:
        args.json_out.write_text(json.dumps(
            {pid: {"old": o, "new": n} for pid, (o, n) in changed.items()}, indent=2))
        print(f"\nper-product detail: {args.json_out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("baseline", "compare"):
        s = sub.add_parser(name)
        s.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
        s.add_argument("--score", action="store_true",
                       help="also capture/diff scores (slower)")
        if name == "compare":
            s.add_argument("--json-out", type=Path, default=None)
    args = p.parse_args(argv)
    return cmd_baseline(args) if args.cmd == "baseline" else cmd_compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
