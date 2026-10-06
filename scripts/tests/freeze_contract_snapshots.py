#!/usr/bin/env python3
"""
Phase 0 — Scoring-snapshot fixture freezer.

Reads the manifest at ``scripts/tests/fixtures/contract_snapshots/_manifest.json``,
extracts the listed products from the current scored output under
``scripts/products/output_<brand>_scored/scored/*.json``, and writes one
``<dsld_id>.json`` fixture per product containing only the fields enumerated
in the manifest's ``frozen_fields`` whitelist.

Invoked by hand when a scoring change has been reviewed and the new
baselines should replace the old ones. The matching test
(``scripts/tests/test_scoring_snapshot_v1.py``) compares the current
scored output against these fixtures on every test run — any drift in
frozen fields fails the test.

Usage:
    python3 scripts/tests/freeze_contract_snapshots.py          # freeze all
    python3 scripts/tests/freeze_contract_snapshots.py 16037    # freeze one by dsld_id
    python3 scripts/tests/freeze_contract_snapshots.py --dry-run
    python3 scripts/tests/freeze_contract_snapshots.py --check --raw-root <dataset-root>

The read-only raw check runs the current production Clean/Enrich/Score owners
for every selected canary, before a full corpus job. It never updates expected
values. After source-based review, --raw-root without --check may refresh a
selected fixture; record the cause in the existing manifest changelog.

Exit codes:
    0 — success, all products frozen
    1 — manifest missing, product missing, or scored output missing
"""

from __future__ import annotations

import argparse
import json
import hashlib
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "scripts" / "tests" / "fixtures" / "contract_snapshots" / "_manifest.json"
FIXTURE_DIR = MANIFEST.parent
PRODUCTS_ROOT = REPO_ROOT / "scripts" / "products"


def load_manifest() -> Dict[str, Any]:
    if not MANIFEST.exists():
        sys.exit(f"ERROR: manifest not found at {MANIFEST}")
    return json.loads(MANIFEST.read_text())


def load_scored_batches(brand_source: str) -> List[Dict[str, Any]]:
    """Load all scored batches for a given brand_source folder name."""
    scored_root = PRODUCTS_ROOT / f"output_{brand_source}_scored" / "scored"
    if not scored_root.exists():
        return []
    products: List[Dict[str, Any]] = []
    for batch in sorted(scored_root.glob("*.json")):
        try:
            data = json.loads(batch.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            products.extend(data)
    return products


def find_product(
    dsld_id: int, brand_source: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Return (product, source_path) or (None, None)."""
    products = load_scored_batches(brand_source)
    for p in products:
        if str(p.get("dsld_id")) == str(dsld_id):
            return p, f"output_{brand_source}_scored/scored"
    return None, None


def freeze_fields(product: Dict[str, Any], whitelist: List[str]) -> Dict[str, Any]:
    """Return a dict containing only the whitelisted keys from product."""
    frozen: Dict[str, Any] = {}
    for k in whitelist:
        if k in product:
            frozen[k] = product[k]
    return frozen


def _walk_diff(
    current: Any, frozen: Any, path: str = "", out: Optional[List[str]] = None
) -> List[str]:
    """Recursively diff two JSON-compatible values; return list of path:value1→value2 lines."""
    if out is None:
        out = []

    if type(current) is not type(frozen):
        # Allow int/float equivalence (e.g. 13.8 vs 13.8)
        if not (
            isinstance(current, (int, float))
            and isinstance(frozen, (int, float))
            and float(current) == float(frozen)
        ):
            out.append(f"  {path or '<root>'}: TYPE {type(frozen).__name__}={frozen!r} -> {type(current).__name__}={current!r}")
            return out

    if isinstance(frozen, dict):
        all_keys = set(frozen.keys()) | set(current.keys())
        for k in sorted(all_keys):
            sub_path = f"{path}.{k}" if path else k
            if k not in frozen:
                out.append(f"  {sub_path}: ADDED {current[k]!r}")
            elif k not in current:
                out.append(f"  {sub_path}: REMOVED (was {frozen[k]!r})")
            else:
                _walk_diff(current[k], frozen[k], sub_path, out)
    elif isinstance(frozen, list):
        if len(current) != len(frozen):
            out.append(f"  {path}: LEN {len(frozen)} -> {len(current)}")
        for i, (c, f) in enumerate(zip(current, frozen)):
            _walk_diff(c, f, f"{path}[{i}]", out)
    else:
        if current != frozen:
            # Tolerance for float rounding (accept 1e-9 drift only)
            if (
                isinstance(current, float)
                and isinstance(frozen, float)
                and abs(current - frozen) < 1e-9
            ):
                return out
            out.append(f"  {path}: {frozen!r} -> {current!r}")
    return out


def _product_diff(
    current: Dict[str, Any], frozen: Dict[str, Any], whitelist: List[str]
) -> List[str]:
    current_restricted = freeze_fields(current, whitelist)
    return _walk_diff(current_restricted, frozen)


@lru_cache(maxsize=1)
def _raw_pipeline():
    # The same three production owners used by the full pipeline, initialized once.
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _score_raw_product(path: Path, dsld_id: int) -> Dict[str, Any]:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads(path.read_text())
    if str(raw.get("id")) != str(dsld_id):
        raise ValueError(f"raw label identity does not match {dsld_id}: {path}")
    normalizer, enricher = _raw_pipeline()
    enriched, errors = enricher.enrich_product(normalizer.normalize_product(deepcopy(raw)))
    if errors:
        raise ValueError(f"enrichment errors for {dsld_id}: {errors}")
    return build_scored_artifact(deepcopy(enriched))


def freeze_one(
    entry: Dict[str, Any], whitelist: List[str], dry_run: bool, *,
    check: bool = False, raw_path: Optional[Path] = None,
) -> Tuple[bool, str]:
    dsld_id = entry["dsld_id"]
    brand_source = entry["brand_source"]
    label = entry.get("label", "")

    product, source = (
        (_score_raw_product(raw_path, dsld_id), str(raw_path))
        if raw_path is not None else find_product(dsld_id, brand_source)
    )
    if product is None:
        return False, f"[{dsld_id:>7}] MISSING from {brand_source} scored output"

    frozen = freeze_fields(product, whitelist)
    fixture_path = FIXTURE_DIR / f"{dsld_id}.json"

    if check:
        if not fixture_path.is_file():
            return False, f"[{dsld_id:>7}] MISSING snapshot {fixture_path}"
        differences = _product_diff(product, json.loads(fixture_path.read_text()), whitelist)
        return not differences, (f"[{dsld_id:>7}] " + ("UNCHANGED" if not differences else
            "DRIFT — review against the source before updating expectations:\n" + "\n".join(differences)))

    if dry_run:
        return True, (
            f"[{dsld_id:>7}] {label[:50]:50s} -> would write "
            f"{fixture_path.name} "
            f"(quality_score_v4_100={frozen.get('quality_score_v4_100')})"
        )

    fixture_path.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    return True, (
        f"[{dsld_id:>7}] {label[:50]:50s} -> wrote {fixture_path.name} "
        f"(quality_score_v4_100={frozen.get('quality_score_v4_100')})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dsld_id", nargs="?", type=int, help="Freeze a single product by dsld_id (default: freeze all)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be written without touching disk")
    parser.add_argument("--check", action="store_true", help="Compare every selected canary without changing any fixture")
    parser.add_argument("--raw-root", type=Path, help="Run raw canaries through current Clean/Enrich/Score instead of reading stored scores")
    args = parser.parse_args()

    manifest = load_manifest()
    whitelist = manifest["fixture_schema"]["frozen_fields"]
    products = manifest["products"]
    identifiers = [str(entry["dsld_id"]) for entry in products]
    if not identifiers or len(set(identifiers)) != len(identifiers):
        print("ERROR: canary manifest must contain nonempty, unique product identities")
        return 1

    if args.dsld_id is not None:
        products = [p for p in products if p["dsld_id"] == args.dsld_id]
        if not products:
            sys.exit(f"ERROR: dsld_id {args.dsld_id} not in manifest")

    raw_paths = {}
    before_fingerprints = None
    raw_hashes = {}
    if args.raw_root is not None:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from pipeline_freshness import stage_input_fingerprints
        before_fingerprints = {stage: stage_input_fingerprints(REPO_ROOT, stage)
                               for stage in ("clean", "enrich", "score")}
        wanted = {str(entry["dsld_id"]) for entry in products}
        for path in args.raw_root.rglob("*.json"):
            if path.stem in wanted:
                raw_paths.setdefault(path.stem, []).append(path)
                raw_hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()

    ok_count = 0
    fail_count = 0
    lines: List[str] = []
    for entry in products:
        paths = raw_paths.get(str(entry["dsld_id"]), [])
        if args.raw_root is not None and len(paths) != 1:
            success, line = False, f"[{entry['dsld_id']:>7}] raw canary requires exactly one input; found {len(paths)} under {args.raw_root}"
        else:
            try:
                success, line = freeze_one(entry, whitelist, args.dry_run,
                    check=args.check, raw_path=paths[0] if args.raw_root is not None else None)
            except Exception as exc:
                success, line = False, f"[{entry['dsld_id']:>7}] FAILED: {type(exc).__name__}: {exc}"
        lines.append(line)
        if success:
            ok_count += 1
        else:
            fail_count += 1

    if before_fingerprints is not None:
        if any(not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest
               for path, digest in raw_hashes.items()):
            fail_count += 1
            lines.append("FAILED: raw canary inputs changed during preflight")
        after = {stage: stage_input_fingerprints(REPO_ROOT, stage) for stage in before_fingerprints}
        if after != before_fingerprints:
            fail_count += 1
            lines.append("FAILED: scoring code/reference inputs changed during preflight")
    print("\n".join(lines))
    print()
    print(f"{'Checked' if args.check else 'Frozen'}: {ok_count}  Failed: {fail_count}  Total: {len(products)}")
    if args.dry_run:
        print("(dry-run; no files written)")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
