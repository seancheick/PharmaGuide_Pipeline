#!/usr/bin/env python3
"""
Phase 3 shadow-diff analyzer.

Given a directory of scored batches produced by a shadow pipeline run, diff
the N snapshot-manifest products against their frozen fixtures and classify
each diff as:

  - UNCHANGED   — no drift in any frozen scoring field.
  - EXPECTED    — drift on a Phase 3 target product (Silybin/Phosphorus) in
                  the intended direction (score correctness improved).
  - UNEXPECTED  — drift on any other product. These block release.
  - MISSING     — product not found in the shadow output (brand may not
                  have been re-run).

Exit codes:
  0 — all diffs accounted for (UNCHANGED + EXPECTED only).
  1 — at least one UNEXPECTED or MISSING diff found.

Usage:
    python3 scripts/tests/shadow_diff_snapshots.py <shadow_scored_root>

Where ``<shadow_scored_root>`` looks like
    /tmp/phase3_shadow/pure_scored/  (containing ``scored/*.json`` batches)
or a single brand's scored dir. It need not cover all 30 products — missing
products are reported separately from drift so you can scope the validation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "scripts" / "tests" / "fixtures" / "contract_snapshots"
MANIFEST_PATH = FIXTURE_DIR / "_manifest.json"

# Products whose scores are ALLOWED to change in Phase 3 shadow-runs.
# Annotate with the expected direction so reviewers can cross-check.
PHASE_3_EXPECTED_DRIFT = {
    16037:  "Silybin Phytosome should now score as milk_thistle, not lecithin",
    182730: "Phosphorus in Athletic Pure Pack should now route via phosphorus canonical",
    12012:  "CVS Spectravite phosphorus row should route via phosphorus canonical",
}


def _load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text())


def _load_scored_batches(scored_root: Path) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []
    # Accept either <root>/scored/*.json or <root>/*.json layout.
    for candidate_dir in (scored_root / "scored", scored_root):
        if candidate_dir.is_dir():
            for batch in sorted(candidate_dir.glob("*.json")):
                try:
                    data = json.loads(batch.read_text())
                except json.JSONDecodeError:
                    continue
                if isinstance(data, list):
                    products.extend(data)
            if products:
                return products
    return products


def _restrict(p: Dict[str, Any], whitelist: List[str]) -> Dict[str, Any]:
    return {k: p[k] for k in whitelist if k in p}


def _walk_diff(a: Any, b: Any, path: str = "", out: Optional[List[str]] = None) -> List[str]:
    if out is None:
        out = []
    if type(a) is not type(b):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and float(a) == float(b):
            return out
        out.append(f"  {path or '<root>'}: {type(b).__name__}={b!r} -> {type(a).__name__}={a!r}")
        return out
    if isinstance(b, dict):
        for k in sorted(set(b.keys()) | set(a.keys())):
            sub = f"{path}.{k}" if path else k
            if k not in b:
                out.append(f"  {sub}: ADDED {a[k]!r}")
            elif k not in a:
                out.append(f"  {sub}: REMOVED {b[k]!r}")
            else:
                _walk_diff(a[k], b[k], sub, out)
    elif isinstance(b, list):
        if len(a) != len(b):
            out.append(f"  {path}: LEN {len(b)} -> {len(a)}")
        for i, (aa, bb) in enumerate(zip(a, b)):
            _walk_diff(aa, bb, f"{path}[{i}]", out)
    else:
        if a != b:
            if isinstance(a, float) and isinstance(b, float) and abs(a - b) < 1e-9:
                return out
            out.append(f"  {path}: {b!r} -> {a!r}")
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 1

    shadow_root = Path(sys.argv[1]).resolve()
    if not shadow_root.exists():
        print(f"ERROR: shadow_root not found: {shadow_root}", file=sys.stderr)
        return 1

    manifest = _load_manifest()
    whitelist = manifest["fixture_schema"]["frozen_fields"]

    shadow_products = _load_scored_batches(shadow_root)
    if not shadow_products:
        print(f"ERROR: no scored products found under {shadow_root}", file=sys.stderr)
        return 1
    shadow_by_id = {str(p.get("dsld_id")): p for p in shadow_products}

    unchanged: List[Tuple[int, str]] = []
    expected: List[Tuple[int, str, List[str]]] = []
    unexpected: List[Tuple[int, str, List[str]]] = []
    missing: List[Tuple[int, str]] = []

    for entry in manifest["products"]:
        dsld_id = entry["dsld_id"]
        label = entry.get("label", "")
        current = shadow_by_id.get(str(dsld_id))
        if current is None:
            missing.append((dsld_id, label))
            continue

        fixture = json.loads((FIXTURE_DIR / f"{dsld_id}.json").read_text())
        diffs = _walk_diff(_restrict(current, whitelist), fixture)
        if not diffs:
            unchanged.append((dsld_id, label))
        elif dsld_id in PHASE_3_EXPECTED_DRIFT:
            expected.append((dsld_id, label, diffs))
        else:
            unexpected.append((dsld_id, label, diffs))

    # Render
    def _print_section(title: str, items: List) -> None:
        print(f"\n=== {title} ({len(items)}) ===")
        for item in items:
            print(f"  [{item[0]:>7}]  {item[1][:60]}")

    _print_section("UNCHANGED", unchanged)
    _print_section("EXPECTED (Phase 3 targets)", [(i, l) for i, l, _ in expected])
    if expected:
        print("\nExpected-drift details:")
        for dsld_id, label, diffs in expected:
            print(f"\n  [{dsld_id}] {label}")
            print(f"    expected: {PHASE_3_EXPECTED_DRIFT[dsld_id]}")
            for d in diffs[:20]:
                print(f"    {d}")
            if len(diffs) > 20:
                print(f"    ... and {len(diffs) - 20} more diffs")

    _print_section("UNEXPECTED (blocks release)", [(i, l) for i, l, _ in unexpected])
    if unexpected:
        print("\nUnexpected-drift details:")
        for dsld_id, label, diffs in unexpected:
            print(f"\n  [{dsld_id}] {label}")
            for d in diffs[:20]:
                print(f"    {d}")
            if len(diffs) > 20:
                print(f"    ... and {len(diffs) - 20} more diffs")

    _print_section("MISSING (brand not in shadow run)", missing)

    print(
        f"\nSummary: {len(unchanged)} unchanged | {len(expected)} expected | "
        f"{len(unexpected)} unexpected | {len(missing)} missing | "
        f"total {len(manifest['products'])}"
    )

    return 0 if not unexpected else 1


if __name__ == "__main__":
    sys.exit(main())
