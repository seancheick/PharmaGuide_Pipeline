"""
Sprint E1.2.4 — inactive-ingredient preservation regression tests.

Defensive-instrumentation posture (per external-dev review 2026-04-22):
a full-catalog scan showed 0 products with real raw inactives being
dropped by the current pipeline. The sprint's original "118 products
affected" figure was a scan-methodology error (counting DSLD's "None"
placeholder as a real inactive). These tests lock in the current
clean state and catch any future regression.

Invariants enforced:
  1. raw_inactives_count emitted on every blob (int, ≥ 0)
  2. "None" placeholder NEVER leaks into blob inactive_ingredients
  3. If raw_inactives_count > 0, blob inactive_ingredients is non-empty
  4. Canary preservation — Plantizyme (capsule, 3 real inactives),
     vitafusion Vit D3 (gummy, many inactives), Transparent Labs KSM-66
     shape (3 real inactives, none lost).

Explicitly out of scope (per sprint discipline):
  * patching DSLD source gaps (e.g. silica missing from upstream)
  * OCR / PDF re-extraction
  * any data invention
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

from scripts.build_final_db import _validate_inactive_preservation  # noqa: E402


# ---------------------------------------------------------------------------
# Validator unit tests
# ---------------------------------------------------------------------------

def test_validator_silent_when_raw_count_is_zero() -> None:
    blob = {"inactive_ingredients": []}
    _validate_inactive_preservation(blob, 0, "DSLD-CLEAN")


def test_validator_silent_when_blob_non_empty_and_raw_positive() -> None:
    blob = {"inactive_ingredients": [{"name": "Gelatin"}, {"name": "Water"}]}
    _validate_inactive_preservation(blob, 2, "DSLD-OK")


def test_validator_raises_on_drop_regression() -> None:
    blob = {"inactive_ingredients": []}
    with pytest.raises(ValueError, match="Filter regression"):
        _validate_inactive_preservation(blob, 3, "DSLD-DROP")


@pytest.mark.parametrize("placeholder_name", ["None", "none", "NONE", "n/a", "N/A", ""])
def test_validator_raises_on_none_placeholder_leak(placeholder_name: str) -> None:
    """The literal "None" string (or N/A variants, or empty) must never
    appear as an inactive_ingredient name."""
    blob = {"inactive_ingredients": [{"name": placeholder_name}]}
    with pytest.raises(ValueError, match="placeholder"):
        _validate_inactive_preservation(blob, 0, "DSLD-LEAK")


def test_validator_skips_non_dict_entries_gracefully() -> None:
    blob = {"inactive_ingredients": [
        "bogus string", None, 42, {"name": "Gelatin"},
    ]}
    _validate_inactive_preservation(blob, 1, "DSLD-MIXED")


# ---------------------------------------------------------------------------
# Canary preservation — real blobs from reports/canary_rebuild/
# ---------------------------------------------------------------------------

CANARY_DIR = ROOT / "reports" / "canary_rebuild"

CANARY_EXPECTATIONS = [
    # (dsld_id, description, expected_raw_count, must_contain_names)
    ("35491", "Plantizyme capsule", 3, {"Hypromellose", "Leucine", "Silicon Dioxide"}),
    ("306237", "Nutricost KSM-66 capsule", None, None),  # count may vary; just no drops
    ("176872", "vitafusion Vitamin D3 gummy", None, {"Sugar", "Gelatin"}),
    ("1002", "GNC Double Strength Fish Oil", None, None),
    ("19067", "Nature Made probiotic", None, None),
    ("1036", "GNC Ultra Mega Gold multi-blend", None, None),
    ("246324", "VitaFusion CBD gummy", None, None),
]


@pytest.mark.parametrize("dsld_id,description,expected_raw,must_contain", CANARY_EXPECTATIONS)
def test_canary_inactives_preserved_and_no_placeholder_leak(
    dsld_id: str, description: str, expected_raw: "int | None", must_contain: "set[str] | None"
) -> None:
    blob_path = CANARY_DIR / f"{dsld_id}.json"
    if not blob_path.exists():
        pytest.skip(f"{dsld_id} canary not rebuilt yet")
    blob = json.loads(blob_path.read_text())

    # Every blob carries raw_inactives_count (int)
    assert "raw_inactives_count" in blob, f"{description} blob missing raw_inactives_count"
    raw_count = blob["raw_inactives_count"]
    assert isinstance(raw_count, int) and raw_count >= 0

    # If raw had inactives, blob must have inactives
    blob_inactives = blob.get("inactive_ingredients") or []
    if raw_count > 0:
        assert len(blob_inactives) > 0, (
            f"{description}: raw_inactives_count={raw_count} but blob is empty"
        )

    # No "None" placeholder leak
    for ing in blob_inactives:
        if not isinstance(ing, dict):
            continue
        name = (ing.get("name") or "").strip().lower()
        assert name not in {"none", "n/a", "na", ""}, (
            f"{description}: placeholder leak {ing.get('name')!r}"
        )

    # Specific count expectation (where pinned)
    if expected_raw is not None:
        assert raw_count == expected_raw, (
            f"{description}: raw_inactives_count={raw_count}, expected {expected_raw}"
        )

    # Named-ingredient expectations (where pinned)
    if must_contain:
        blob_names = {
            (ing.get("name") or "").strip()
            for ing in blob_inactives if isinstance(ing, dict)
        }
        missing = must_contain - blob_names
        assert not missing, f"{description}: missing inactives {missing}"


# ---------------------------------------------------------------------------
# raw_inactives_count normalization — "None" placeholder not counted
# ---------------------------------------------------------------------------

def test_normalizer_excludes_none_placeholder_from_raw_count() -> None:
    """Emission at clean-time filters name='None' from the raw count so
    DSLD products with no disclosed inactives correctly report 0."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402

    normalizer = EnhancedDSLDNormalizer()
    # DSLD-shape raw with only the "None" placeholder
    raw_with_placeholder_only = {
        "id": "TEST-1",
        "ingredientRows": [],
        "otheringredients": {
            "text": None,
            "ingredients": [
                {"order": 1, "ingredientId": 5923, "name": "None",
                 "category": "other", "ingredientGroup": "None"}
            ],
        },
    }
    cleaned = normalizer.normalize_product(raw_with_placeholder_only)
    assert cleaned.get("raw_inactives_count") == 0


def test_normalizer_counts_real_inactives_excluding_none() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402

    normalizer = EnhancedDSLDNormalizer()
    raw_mixed = {
        "id": "TEST-2",
        "ingredientRows": [],
        "otheringredients": {
            "text": None,
            "ingredients": [
                {"order": 1, "ingredientId": 1, "name": "None",           # excluded
                 "category": "other", "ingredientGroup": "None"},
                {"order": 2, "ingredientId": 2, "name": "Hypromellose",  # counted
                 "category": "other", "ingredientGroup": "Hypromellose"},
                {"order": 3, "ingredientId": 3, "name": "Magnesium Stearate",  # counted
                 "category": "mineral", "ingredientGroup": "Magnesium"},
                {"order": 4, "ingredientId": 4, "name": "",              # excluded (empty)
                 "category": "other"},
            ],
        },
    }
    cleaned = normalizer.normalize_product(raw_mixed)
    assert cleaned.get("raw_inactives_count") == 2


# ---------------------------------------------------------------------------
# 2026-05-14 — Phase 4a intentional_drops reconciliation
# ---------------------------------------------------------------------------
# Background: build_final_db's inactive-emission loop drops entries where
# the resolver returns is_label_descriptor=True or is_active_only=True
# (Phase 4a, 2026-04-30). For products where the ONLY raw inactive is
# such an entry (e.g., Garden of Life MCT Oil → "Coconut" source
# descriptor), the validator used to fire spuriously: raw_inactives_count=1
# but blob_inactives=0. Bucket 2 closure (handoff doc) added the
# `intentional_drops` parameter so the validator subtracts these
# legitimate drops before checking the preservation invariant.

def test_validator_silent_when_only_intentional_drops_explain_empty_blob() -> None:
    """The Garden of Life MCT Oil case (dsld 327403/329092):
    1 raw inactive ("Coconut") got dropped because the resolver flagged
    it as is_label_descriptor=True (Coconut is a source descriptor for
    the MCT, which IS the product's active). Validator must accept this."""
    blob = {"inactive_ingredients": []}
    # No raise expected — the one raw inactive was an intentional drop.
    _validate_inactive_preservation(
        blob, raw_inactives_count=1, dsld_id="DSLD-MCT-OIL",
        intentional_drops=1,
    )


def test_validator_still_raises_when_some_drops_are_intentional_but_others_lost() -> None:
    """If 3 raw inactives, only 1 is an intentional drop, and the blob is
    empty, that's still a regression (2 entries got lost somewhere)."""
    blob = {"inactive_ingredients": []}
    with pytest.raises(ValueError, match="Filter regression"):
        _validate_inactive_preservation(
            blob, raw_inactives_count=3, dsld_id="DSLD-PARTIAL-LOSS",
            intentional_drops=1,
        )


def test_validator_error_message_reports_intentional_drops() -> None:
    """The error message includes the intentional_drops count so future
    debuggers can see at a glance how many were legitimately filtered
    versus how many disappeared unexplained."""
    blob = {"inactive_ingredients": []}
    with pytest.raises(ValueError) as ei:
        _validate_inactive_preservation(
            blob, raw_inactives_count=2, dsld_id="DSLD-DEBUG",
            intentional_drops=0,
        )
    # Original "filter regression" message preserved
    assert "Filter regression" in str(ei.value)
    # New: count details visible
    assert "2 real" in str(ei.value)
    assert "0 intentionally dropped" in str(ei.value)
    assert "2 net" in str(ei.value)


def test_validator_default_intentional_drops_is_zero_for_back_compat() -> None:
    """Old call sites that don't pass intentional_drops must behave
    exactly as before — defaulting to 0 means the invariant is unchanged."""
    blob = {"inactive_ingredients": []}
    with pytest.raises(ValueError, match="Filter regression"):
        # Note: no intentional_drops kwarg — relies on default
        _validate_inactive_preservation(blob, 1, "DSLD-LEGACY-CALL")


def test_validator_silent_when_intentional_drops_exceed_raw_count() -> None:
    """Edge case: if for some reason intentional_drops > raw_count
    (shouldn't happen with correct accounting, but defensive),
    the validator must not raise — empty blob is still acceptable."""
    blob = {"inactive_ingredients": []}
    _validate_inactive_preservation(
        blob, raw_inactives_count=1, dsld_id="DSLD-OVER-COUNT",
        intentional_drops=2,
    )
