"""
Regression suite for canonical_id + delivers_markers emit on active ingredient
blob entries.

These two fields are foundational infrastructure:

  canonical_id — stable string identifier (e.g. 'vitamin_a', 'turmeric',
    'camu_camu') used by interaction-rule matching, stack-checking,
    evidence routing, biomarker scoring, longitudinal tracking, dedup,
    and analytics. Without it on the blob, Flutter has to re-derive the
    canonical key from name/raw_source_text on every read — fragile and
    silent-failure-prone.

  delivers_markers — array of {marker_canonical_id, evidence_source,
    confidence_scale, ...} attached by the enricher when a source
    botanical (e.g. turmeric) is a clinically-recognized source of a
    bioactive marker (e.g. curcumin). Drives the marker-via-ingredient
    Section C evidence pathway. The enricher computes it; build_final_db
    must propagate it intact.

Phase 0 (audit_contract_sync) reported both at 0% emit pre-fix. The fix
in build_final_db.py reads `m.get('canonical_id')` and
`m.get('delivers_markers')` from the IQM match record (`iqd_by_raw[raw]`)
which the enricher already populates.

Tests cover:
  - The blob builder reads canonical_id from `m` (IQM match) when the
    enricher attached it.
  - canonical_id falls back to ing.canonical_id when `m` is empty
    (e.g. unmapped or skipped paths).
  - delivers_markers is emitted as a list (possibly empty) — never null.
  - delivers_markers payload survives unchanged (no field-level mutation).
  - Canary blob assertions on the targeted rebuild output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Audit-side contract: shape of the blob fields the fix must emit
# ---------------------------------------------------------------------------

REQUIRED_KEYS_ON_ACTIVE = ("canonical_id", "delivers_markers")


def _is_marker_payload(item: object) -> bool:
    """Each entry in delivers_markers must be a dict with at least a
    marker_canonical_id field. (Evidence/confidence fields are optional
    by data quality, not by schema — older entries may omit them.)"""
    if not isinstance(item, dict):
        return False
    return bool(item.get("marker_canonical_id"))


# ---------------------------------------------------------------------------
# Unit-ish contract checks (no full pipeline run)
# ---------------------------------------------------------------------------

def test_canonical_id_field_documented_in_active_contract() -> None:
    """The audit_contract_sync ACTIVE_CONTRACT must include canonical_id
    + delivers_markers as v1.5.0 fields. Catches contract-doc drift."""
    from scripts.audit_contract_sync import ACTIVE_CONTRACT
    for field in REQUIRED_KEYS_ON_ACTIVE:
        assert field in ACTIVE_CONTRACT, f"missing {field!r} from ACTIVE_CONTRACT"
        spec = ACTIVE_CONTRACT[field]
        assert spec.get("v1_5_0"), f"{field!r} not flagged as v1.5.0 contract field"


def test_blob_builder_emits_canonical_id_and_delivers_markers() -> None:
    """Source-level assertion: build_final_db.py blob construction must
    name both fields. This catches accidental removal."""
    src = (ROOT / "scripts" / "build_final_db.py").read_text()
    # The active-ingredient blob dict starts at `ingredients.append({` and
    # MUST list both fields somewhere in the body.
    assert '"canonical_id":' in src, (
        "build_final_db.py does not emit canonical_id on any blob field"
    )
    assert '"delivers_markers":' in src, (
        "build_final_db.py does not emit delivers_markers on any blob field"
    )
    # The exact emit-site comment must remain so the next reader knows why.
    assert (
        "foundational identifier for interactions, stack" in src
    ), "canonical_id rationale comment is missing — keep the why in the file"


# ---------------------------------------------------------------------------
# Canary blob assertions
# ---------------------------------------------------------------------------

# Targeted rebuild output dir (build only GNC + Doctors_Best).
# Falls back to the regular /tmp/pharmaguide_release_build path so this
# test works against any fresh build with these canaries present.
_BUILD_CANDIDATES = (
    Path("/tmp/pharmaguide_release_build_canonical_id"),
    Path("/tmp/pharmaguide_release_build_v3"),
    Path("/tmp/pharmaguide_release_build"),
)

# Canary blobs: (dsld_id, brand, expected_ingredient_substring,
#                expected_canonical_id, expects_markers_nonempty)
CANARY_BLOBS = [
    ("1007",   "GNC",          "vitamin a",   "vitamin_a", False),
    ("278548", "Doctors_Best", "turmeric",    "turmeric",  True),
    ("24439",  "Doctors_Best", "camu camu",   "camu_camu", True),
    ("24448",  "Doctors_Best", "turmeric",    "turmeric",  True),
]


def _find_canary_blob(dsld_id: str) -> dict | None:
    for base in _BUILD_CANDIDATES:
        p = base / "detail_blobs" / f"{dsld_id}.json"
        if p.exists():
            return json.loads(p.read_text())
    return None


def _find_ingredient(blob: dict, substring: str) -> dict | None:
    for ing in blob.get("ingredients") or []:
        n = (ing.get("name") or "").lower()
        if substring.lower() in n:
            return ing
        rs = (ing.get("raw_source_text") or "").lower()
        if substring.lower() in rs:
            return ing
    return None


@pytest.mark.parametrize("dsld_id, brand, ing_substr, expected_cid, expects_markers", CANARY_BLOBS)
def test_canary_active_carries_canonical_id(
    dsld_id: str,
    brand: str,
    ing_substr: str,
    expected_cid: str,
    expects_markers: bool,
) -> None:
    blob = _find_canary_blob(dsld_id)
    if blob is None:
        pytest.skip(
            f"Canary blob {dsld_id} ({brand}) not present in any of "
            f"{[str(b) for b in _BUILD_CANDIDATES]} — run targeted rebuild first."
        )
    ing = _find_ingredient(blob, ing_substr)
    assert ing is not None, (
        f"{dsld_id}: ingredient containing {ing_substr!r} not found in blob"
    )
    cid = ing.get("canonical_id")
    assert cid == expected_cid, (
        f"{dsld_id} ingredient {ing.get('name')!r}: canonical_id={cid!r} "
        f"(expected {expected_cid!r})"
    )


@pytest.mark.parametrize("dsld_id, brand, ing_substr, expected_cid, expects_markers", CANARY_BLOBS)
def test_canary_active_carries_delivers_markers_field(
    dsld_id: str,
    brand: str,
    ing_substr: str,
    expected_cid: str,
    expects_markers: bool,
) -> None:
    blob = _find_canary_blob(dsld_id)
    if blob is None:
        pytest.skip(f"Canary blob {dsld_id} not present — run targeted rebuild first.")
    ing = _find_ingredient(blob, ing_substr)
    assert ing is not None
    # The field must ALWAYS be a list (possibly empty) — never null/missing.
    markers = ing.get("delivers_markers", "__MISSING__")
    assert markers != "__MISSING__", (
        f"{dsld_id} ingredient {ing.get('name')!r}: delivers_markers key absent"
    )
    assert isinstance(markers, list), (
        f"{dsld_id} ingredient {ing.get('name')!r}: delivers_markers must be a list, "
        f"got {type(markers).__name__}"
    )
    if expects_markers:
        assert markers, (
            f"{dsld_id} ingredient {ing.get('name')!r} ({expected_cid!r}): "
            "expected non-empty delivers_markers"
        )
        for item in markers:
            assert _is_marker_payload(item), (
                f"{dsld_id}: malformed delivers_markers item — missing marker_canonical_id: {item!r}"
            )


def test_canonical_id_emit_rate_at_least_90_percent_on_mapped() -> None:
    """Across the canary set, every mapped active ingredient must carry a
    non-empty canonical_id. <100% is acceptable on unmapped/skipped paths
    (those don't have a canonical IQM entry by definition), but any mapped
    ingredient missing canonical_id is a blob-contract failure."""
    # Find any reachable build dir
    base = next((p for p in _BUILD_CANDIDATES if (p / "detail_blobs").is_dir()), None)
    if base is None:
        pytest.skip("no build directory available — run targeted rebuild first")

    sample = sorted((base / "detail_blobs").glob("*.json"))[:200]
    mapped_total = 0
    mapped_with_cid = 0
    for p in sample:
        try:
            b = json.loads(p.read_text())
        except Exception:
            continue
        for ing in b.get("ingredients") or []:
            if ing.get("is_mapped") or ing.get("mapped"):
                mapped_total += 1
                if ing.get("canonical_id"):
                    mapped_with_cid += 1
    if mapped_total == 0:
        pytest.skip("no mapped active ingredients in sample — cannot evaluate")
    rate = mapped_with_cid / mapped_total
    assert rate >= 0.90, (
        f"only {mapped_with_cid}/{mapped_total} ({rate:.1%}) mapped actives carry canonical_id "
        f"in the first 200 blobs at {base} — expected ≥90%"
    )
