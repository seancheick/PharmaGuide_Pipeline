#!/usr/bin/env python3
"""Score the whole corpus and write one line per product (read-only).

Half of an A/B. Run it from two trees against the SAME corpus, then diff the two
snapshots with --diff. Two processes rather than one, because the change under
test is in imported module code: simulating "before" from "after" would mean
reconstructing the old rule from the new one's output, which is exactly the kind
of re-derivation that produced a wrong answer earlier in this project.

    # from a worktree at the parent commit
    scoring_ab_snapshot.py --products-root <corpus> --out before.jsonl
    # from the tree under test
    scoring_ab_snapshot.py --products-root <corpus> --out after.jsonl
    scoring_ab_snapshot.py --diff before.jsonl after.jsonl --report AB.md

The corpus root is an argument so a clean worktree - which has no
scripts/products of its own - can score the canonical corpus instead of
silently scoring nothing.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))


def snapshot(products_root: Path, out_path: Path) -> int:
    from score_supplements_v4 import score_product_v4

    written = 0
    with out_path.open("w") as sink:
        for brand_path in sorted(glob.glob(str(products_root / "output_*_enriched/enriched/*.json"))):
            for enriched in json.load(open(brand_path)):
                result = score_product_v4(json.loads(json.dumps(enriched)))
                pillars = result.get("quality_pillars_v4") or {}
                evidence = pillars.get("evidence") or {}
                safety = pillars.get("safety_hygiene") or {}
                module_bd = (result.get("v4_breakdown") or {}).get("module") or {}
                formulation_bd = ((module_bd.get("dimensions") or {})
                                  .get("formulation") or {})
                sugar = (formulation_bd.get("metadata") or {}).get("dietary_sugar") or {}
                form_pen = formulation_bd.get("penalties") or {}
                sink.write(json.dumps({
                    "dsld_id": str(enriched.get("dsld_id")),
                    "brand_dir": Path(brand_path).parents[1].name,
                    "module": result.get("v4_module"),
                    "evidence": evidence.get("score"),
                    "evidence_reason": evidence.get("reason"),
                    "total": result.get("quality_score_v4_100"),
                    "tier": result.get("quality_tier"),
                    # Every public pillar, so a diff can prove that a change
                    # confined to one owner did not move any other pillar.
                    "pillars": {name: (block or {}).get("score")
                                for name, block in pillars.items()},
                    # The dietary-sugar owner's own determination, so a sugar
                    # A/B reports branch transitions rather than inferring them.
                    "sugar_penalty": sugar.get("penalty"),
                    "sugar_reason": sugar.get("reason"),
                    "sugar_level": sugar.get("level"),
                    "canonical_finds_no_sugar": sugar.get("canonical_finds_no_sugar"),
                    "contains_sugar": sugar.get("contains_sugar"),
                    "has_added_sugar": sugar.get("has_added_sugar"),
                    "n_high_glycemic": len(sugar.get("high_glycemic_sweeteners") or []),
                    "n_sugar_alcohols": len(sugar.get("sugar_alcohols") or []),
                    "n_syrup_sources": len(sugar.get("syrup_sources") or []),
                    "b1_dietary_sugar": form_pen.get("B1_dietary_sugar"),
                    "b1_harmful_additives": form_pen.get("B1_harmful_additives"),
                    "safety_reason": safety.get("reason"),
                    "safety_components": safety.get("components") or {},
                }) + "\n")
                written += 1
            if written and written % 2000 < 50:
                print(f"  {written} scored", file=sys.stderr, flush=True)
    print(f"{written} products scored -> {out_path}", file=sys.stderr)
    return written


def _load(path: Path) -> dict:
    return {row["dsld_id"]: row for row in map(json.loads, path.open())}


def diff(before_path: Path, after_path: Path, report: Path | None) -> int:
    before, after = _load(before_path), _load(after_path)
    only_before = sorted(set(before) - set(after))
    only_after = sorted(set(after) - set(before))

    evidence_movers, total_movers, tier_movers, reason_only = [], [], [], []
    tier_transitions = collections.Counter()
    by_module = collections.Counter()
    for dsld_id, new in after.items():
        old = before.get(dsld_id)
        if old is None:
            continue
        ev_delta = None
        if old["evidence"] is not None and new["evidence"] is not None:
            ev_delta = round(new["evidence"] - old["evidence"], 4)
        total_delta = None
        if old["total"] is not None and new["total"] is not None:
            total_delta = round(new["total"] - old["total"], 4)
        moved = bool(ev_delta) or bool(total_delta) or old["tier"] != new["tier"]
        row = {"dsld_id": dsld_id, "brand_dir": new["brand_dir"], "module": new["module"],
               "evidence_before": old["evidence"], "evidence_after": new["evidence"],
               "evidence_delta": ev_delta, "total_before": old["total"],
               "total_after": new["total"], "total_delta": total_delta,
               "tier_before": old["tier"], "tier_after": new["tier"],
               "reason_before": old["evidence_reason"], "reason_after": new["evidence_reason"]}
        if moved:
            by_module[new["module"]] += 1
            if ev_delta:
                evidence_movers.append(row)
            if total_delta:
                total_movers.append(row)
            if old["tier"] != new["tier"]:
                tier_movers.append(row)
                tier_transitions[f"{old['tier']} -> {new['tier']}"] += 1
        elif old["evidence_reason"] != new["evidence_reason"]:
            # The explanation changed while every number stayed identical. This
            # is the truthfulness correction, and it is counted separately so it
            # is never mistaken for a scoring movement.
            reason_only.append(row)

    ev_deltas = [r["evidence_delta"] for r in evidence_movers if r["evidence_delta"] is not None]
    summary = {
        "products_before": len(before), "products_after": len(after),
        "only_in_before": only_before[:20], "only_in_after": only_after[:20],
        "evidence_movers": len(evidence_movers),
        "final_score_movers": len(total_movers),
        "tier_movers": len(tier_movers),
        "explanation_only_corrections": len(reason_only),
        "tier_transitions": dict(tier_transitions.most_common()),
        "movers_by_module": dict(by_module.most_common()),
        "evidence_delta_min": min(ev_deltas) if ev_deltas else None,
        "evidence_delta_max": max(ev_deltas) if ev_deltas else None,
        "evidence_increases": sum(1 for d in ev_deltas if d > 0),
        "evidence_decreases": sum(1 for d in ev_deltas if d < 0),
        "largest_decreases": sorted(evidence_movers,
                                    key=lambda r: r["evidence_delta"] or 0)[:10],
        "largest_increases": sorted(evidence_movers,
                                    key=lambda r: -(r["evidence_delta"] or 0))[:10],
    }
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("largest_decreases", "largest_increases")}, indent=1))
    if report:
        (OUT / report if not Path(report).is_absolute() else Path(report)).write_text(
            json.dumps({"_summary": summary, "evidence_movers": evidence_movers,
                        "explanation_only_corrections": reason_only}, indent=1))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--products-root", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--diff", nargs=2, type=Path, metavar=("BEFORE", "AFTER"))
    parser.add_argument("--report")
    args = parser.parse_args()

    if args.diff:
        return diff(args.diff[0], args.diff[1], args.report)
    if not args.products_root or not args.out:
        parser.error("--products-root and --out are required unless --diff is given")
    if not args.products_root.exists():
        parser.error(f"corpus root does not exist: {args.products_root}")
    snapshot(args.products_root, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
