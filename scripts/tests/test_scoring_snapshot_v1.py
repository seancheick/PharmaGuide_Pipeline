"""
Phase 0 — Scoring-snapshot regression test.

For the 30 diverse products listed in
``scripts/tests/fixtures/contract_snapshots/_manifest.json``, this test re-loads
the current scored output from ``scripts/products/output_<brand>_scored/scored/``
and asserts the scoring-critical fields match the frozen fixtures in
``scripts/tests/fixtures/contract_snapshots/<dsld_id>.json``.

Why: Phase 3 (enricher reads ``canonical_id`` authoritatively) will intentionally
change scores on Silybin Phytosome, Phosphorus-containing multivitamins, and any
other product whose text-inferred parent differed from the cleaner's
canonical_id. Every other score must stay stable. This snapshot diff is our
regression safety net — unexpected drift is a bug, expected drift is gated
through ``freeze_contract_snapshots.py`` + a changelog entry in the manifest.

To regenerate after a reviewed scoring change:

    python3 scripts/tests/freeze_contract_snapshots.py <dsld_id>
    # then append a changelog entry to _manifest.json documenting the change

See docs/HANDOFF_2026-04-20_PIPELINE_REFACTOR.md § Phase 0 for context.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "scripts" / "tests" / "fixtures" / "contract_snapshots"
MANIFEST_PATH = FIXTURE_DIR / "_manifest.json"
PRODUCTS_ROOT = REPO_ROOT / "scripts" / "products"


# ---------------------------------------------------------------------------
# Fixture loaders
# ---------------------------------------------------------------------------


def _load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text())


def _load_fixture(dsld_id: int) -> Dict[str, Any]:
    return json.loads((FIXTURE_DIR / f"{dsld_id}.json").read_text())


_SCORED_CACHE: Dict[str, List[Dict[str, Any]]] = {}


def _load_scored_batches(brand_source: str) -> List[Dict[str, Any]]:
    """Cache-friendly scored output loader; one disk read per brand per session."""
    if brand_source in _SCORED_CACHE:
        return _SCORED_CACHE[brand_source]
    scored_root = PRODUCTS_ROOT / f"output_{brand_source}_scored" / "scored"
    products: List[Dict[str, Any]] = []
    if scored_root.exists():
        for batch in sorted(scored_root.glob("*.json")):
            try:
                data = json.loads(batch.read_text())
            except json.JSONDecodeError:
                continue
            if isinstance(data, list):
                products.extend(data)
    _SCORED_CACHE[brand_source] = products
    return products


def _find_current_product(
    dsld_id: int, brand_source: str
) -> Optional[Dict[str, Any]]:
    for p in _load_scored_batches(brand_source):
        if str(p.get("dsld_id")) == str(dsld_id):
            return p
    return None


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------


def _restrict_to_whitelist(
    product: Dict[str, Any], whitelist: List[str]
) -> Dict[str, Any]:
    return {k: product[k] for k in whitelist if k in product}


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
    current_restricted = _restrict_to_whitelist(current, whitelist)
    return _walk_diff(current_restricted, frozen)


# ---------------------------------------------------------------------------
# Parametrized tests (one per product)
# ---------------------------------------------------------------------------


def _snapshot_params() -> List[Tuple[int, str, str]]:
    manifest = _load_manifest()
    return [
        (p["dsld_id"], p["brand_source"], p.get("label", ""))
        for p in manifest["products"]
    ]


@pytest.mark.parametrize("dsld_id,brand_source,label", _snapshot_params())
def test_scored_product_matches_snapshot(
    dsld_id: int, brand_source: str, label: str
) -> None:
    """Each frozen product's scoring fields must match the current scored output exactly."""
    manifest = _load_manifest()
    whitelist = manifest["fixture_schema"]["frozen_fields"]

    current = _find_current_product(dsld_id, brand_source)
    assert current is not None, (
        f"Product {dsld_id} ({label}) missing from {brand_source} scored output. "
        f"Re-run the pipeline for this brand."
    )

    frozen = _load_fixture(dsld_id)
    diffs = _product_diff(current, frozen, whitelist)

    assert not diffs, (
        f"\nScoring snapshot drift for {dsld_id} — {label}\n"
        f"  brand_source: {brand_source}\n"
        f"  fixture: {FIXTURE_DIR / f'{dsld_id}.json'}\n\n"
        f"Drift:\n" + "\n".join(diffs) + "\n\n"
        f"If this drift is INTENTIONAL (e.g. Phase 3 Silybin/Phosphorus fix):\n"
        f"  1. Review each drift line\n"
        f"  2. python3 scripts/tests/freeze_contract_snapshots.py {dsld_id}\n"
        f"  3. Add a changelog entry to {MANIFEST_PATH} documenting the fix\n"
        f"If UNINTENTIONAL: revert the code change that caused the drift."
    )


def test_manifest_matches_fixtures_on_disk() -> None:
    """Every product in manifest has a fixture file, and no orphan fixtures exist."""
    manifest = _load_manifest()
    manifest_ids = {p["dsld_id"] for p in manifest["products"]}
    fixture_ids = {
        int(f.stem)
        for f in FIXTURE_DIR.glob("*.json")
        if f.name != "_manifest.json" and f.stem.isdigit()
    }
    missing = manifest_ids - fixture_ids
    orphan = fixture_ids - manifest_ids
    assert not missing, (
        f"Products in manifest but missing fixture file: {sorted(missing)}. "
        f"Run: python3 scripts/tests/freeze_contract_snapshots.py"
    )
    assert not orphan, (
        f"Orphan fixture files with no manifest entry: {sorted(orphan)}. "
        f"Either add to manifest or delete the .json file."
    )


def test_manifest_schema_valid() -> None:
    """Manifest must carry the required top-level fields."""
    manifest = _load_manifest()
    for required in ("schema_version", "frozen_on", "fixture_schema", "products", "changelog"):
        assert required in manifest, f"manifest missing key: {required}"
    assert "frozen_fields" in manifest["fixture_schema"]
    assert isinstance(manifest["products"], list)
    assert len(manifest["products"]) >= 20, (
        f"Snapshot manifest should cover at least 20 diverse products; "
        f"currently {len(manifest['products'])}"
    )
    for p in manifest["products"]:
        assert "dsld_id" in p
        assert "brand_source" in p
        assert "label" in p
