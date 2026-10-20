#!/usr/bin/env python3
"""Cleaner safety-classification equivalence probe (PR #176 follow-up).

PR #176 removed the cleaner's fuzzy fallback; its whole-corpus "0 diffs" check
lived only in a session scratchpad. This probe makes the check repeatable: it
runs ``EnhancedDSLDNormalizer._priority_based_classification`` from one
checkout over a fixed name set and writes the banned/harmful/allergen results.
Run it once per checkout, then ``compare`` the two outputs.

Name set: every distinct ingredient row name in a frozen raw cohort, plus each
allergens.json standard name and alias with prefix, suffix and one-letter typo
variants (the shapes a fuzzy matcher would have caught).

    python3 probe.py run --scripts-dir <checkout>/scripts --raw-dir <frozen_raw> --out a.json
    python3 probe.py compare a.json b.json
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

FIELDS = ("banned_info", "harmful_info", "allergen_info")
PREFIXES = ("organic ", "natural ", "hydrolyzed ")
SUFFIXES = (" powder", " extract", " oil", " (non-gmo)", "s")


def _row_names(node, out):
    if isinstance(node, dict):
        name = node.get("name")
        if isinstance(name, str) and name.strip():
            out.add(name.strip())
        for value in node.values():
            _row_names(value, out)
    elif isinstance(node, list):
        for value in node:
            _row_names(value, out)


def _typos(term):
    """Drop one interior letter and swap one adjacent pair."""
    if len(term) < 5:
        return set()
    mid = len(term) // 2
    return {term[:mid] + term[mid + 1:], term[:mid] + term[mid + 1] + term[mid] + term[mid + 2:]}


def build_names(raw_dir, allergens_path):
    labels = sorted(Path(raw_dir).rglob("*.json"))
    if not labels:
        # Allergen variants alone would compare clean without auditing any label.
        raise SystemExit(f"no raw label JSON under {raw_dir}")
    names = set()
    for path in labels:
        label = json.loads(path.read_text(encoding="utf-8"))
        for section in ("ingredientRows", "otheringredients"):
            _row_names(label.get(section), names)
    allergens = json.loads(Path(allergens_path).read_text(encoding="utf-8"))["allergens"]
    for entry in allergens:
        for term in [entry["standard_name"], *entry.get("aliases", [])]:
            term = term.lower()
            names.add(term)
            names.update(p + term for p in PREFIXES)
            names.update(term + s for s in SUFFIXES)
            names.update(_typos(term))
    return sorted(names)


def run(args):
    scripts_dir = Path(args.scripts_dir).resolve()
    sys.path.insert(0, str(scripts_dir))
    from enhanced_normalizer import EnhancedDSLDNormalizer

    names = build_names(args.raw_dir, scripts_dir / "data" / "allergens.json")
    normalizer = EnhancedDSLDNormalizer()
    results = {}
    for name in names:
        classified = normalizer._priority_based_classification(name, [])
        results[name] = {field: classified[field] for field in FIELDS}
    Path(args.out).write_text(json.dumps(results, indent=1, sort_keys=True), encoding="utf-8")
    flagged = {
        "banned": sum(1 for r in results.values() if r["banned_info"]["is_banned"]),
        "harmful": sum(1 for r in results.values() if r["harmful_info"]["category"] != "none"),
        "allergen": sum(1 for r in results.values() if r["allergen_info"]["is_allergen"]),
    }
    raw_labels = len(list(Path(args.raw_dir).rglob("*.json")))
    print(json.dumps({"names": len(results), "raw_labels": raw_labels, "flagged": flagged}, sort_keys=True))


def compare(args):
    left = json.loads(Path(args.left).read_text(encoding="utf-8"))
    right = json.loads(Path(args.right).read_text(encoding="utf-8"))
    diffs = sorted(
        name for name in set(left) | set(right) if left.get(name) != right.get(name)
    )
    report = {
        "left": {"names": len(left), "sha256": hashlib.sha256(Path(args.left).read_bytes()).hexdigest()},
        "right": {"names": len(right), "sha256": hashlib.sha256(Path(args.right).read_bytes()).hexdigest()},
        "changed": len(diffs),
        "changed_names": diffs[:50],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if diffs else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--scripts-dir", required=True)
    run_p.add_argument("--raw-dir", required=True)
    run_p.add_argument("--out", required=True)
    cmp_p = sub.add_parser("compare")
    cmp_p.add_argument("left")
    cmp_p.add_argument("right")
    args = parser.parse_args()
    if args.cmd == "run":
        run(args)
        return 0
    return compare(args)


if __name__ == "__main__":
    sys.exit(main())
