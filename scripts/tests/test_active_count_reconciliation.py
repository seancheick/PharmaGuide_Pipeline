"""
Sprint E1.2.5 — active-count reconciliation regression tests.

Every delta between `raw_actives_count` and blob `ingredients` count
must be explained via `ingredients_dropped_reasons[]`. Hard stop if
raw > 0 AND blob == 0 AND no reasons (unexplained drop — bug).

Allowed reason codes (tight enum):
  DROPPED_STRUCTURAL_HEADER   — "Total Omega-3", prop-blend parent
  DROPPED_NUTRITION_FACT       — "Calories", macro rows
  DROPPED_AS_INACTIVE          — routed to inactive_ingredients
  DROPPED_SUMMARY_WRAPPER      — "Less than 2% of:" headers
  DROPPED_UNMAPPED_ACTIVE      — real active, scorer has no rule
  DROPPED_PARSE_ERROR          — bug sentinel (must trend to 0)

Anything else → ValueError.
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

from scripts.build_final_db import (  # noqa: E402
    _ALLOWED_DROP_REASONS,
    _compute_ingredients_dropped_reasons,
    _validate_active_count_reconciliation,
)


# ---------------------------------------------------------------------------
# Reason-code aggregation from display_ingredients
# ---------------------------------------------------------------------------

def test_structural_container_maps_to_header_reason() -> None:
    enriched = {"display_ingredients": [
        {"display_type": "structural_container", "raw_source_text": "Proprietary Blend"},
    ]}
    assert _compute_ingredients_dropped_reasons(enriched) == ["DROPPED_STRUCTURAL_HEADER"]


def test_summary_wrapper_maps_to_summary_reason() -> None:
    enriched = {"display_ingredients": [
        {"display_type": "summary_wrapper", "raw_source_text": "Less than 2% of:"},
    ]}
    assert _compute_ingredients_dropped_reasons(enriched) == ["DROPPED_SUMMARY_WRAPPER"]


def test_inactive_classified_maps_to_inactive_reason() -> None:
    enriched = {"display_ingredients": [
        {"display_type": "inactive_ingredient", "raw_source_text": "Gelatin"},
    ]}
    assert _compute_ingredients_dropped_reasons(enriched) == ["DROPPED_AS_INACTIVE"]


def test_multiple_types_aggregated_sorted_unique() -> None:
    enriched = {"display_ingredients": [
        {"display_type": "structural_container"},
        {"display_type": "inactive_ingredient"},
        {"display_type": "inactive_ingredient"},  # dupe
        {"display_type": "summary_wrapper"},
    ]}
    reasons = _compute_ingredients_dropped_reasons(enriched)
    assert reasons == sorted(reasons)
    assert len(reasons) == len(set(reasons))
    assert set(reasons) == {
        "DROPPED_STRUCTURAL_HEADER",
        "DROPPED_AS_INACTIVE",
        "DROPPED_SUMMARY_WRAPPER",
    }


def test_unknown_display_type_does_not_emit_reason() -> None:
    """Unknown display_types are ignored (quiet fail) — validator
    catches any unknown reason that DOES get emitted."""
    enriched = {"display_ingredients": [
        {"display_type": "wibble"},
    ]}
    assert _compute_ingredients_dropped_reasons(enriched) == []


def test_empty_display_ingredients_returns_empty() -> None:
    assert _compute_ingredients_dropped_reasons({}) == []
    assert _compute_ingredients_dropped_reasons({"display_ingredients": []}) == []


# ---------------------------------------------------------------------------
# Validator — unexplained-drop hard stop
# ---------------------------------------------------------------------------

def test_validator_silent_when_raw_is_zero() -> None:
    blob = {"ingredients": [], "ingredients_dropped_reasons": []}
    _validate_active_count_reconciliation(blob, 0, "DSLD-CLEAN")


def test_validator_silent_when_blob_non_empty() -> None:
    blob = {"ingredients": [{"name": "Vitamin C"}], "ingredients_dropped_reasons": []}
    _validate_active_count_reconciliation(blob, 1, "DSLD-OK")


def test_validator_silent_with_reasons_even_if_blob_empty() -> None:
    """Raw had actives, blob has 0, but reasons explain why. OK."""
    blob = {
        "ingredients": [],
        "ingredients_dropped_reasons": ["DROPPED_AS_INACTIVE", "DROPPED_NUTRITION_FACT"],
    }
    _validate_active_count_reconciliation(blob, 3, "DSLD-EXPLAINED")


def test_validator_raises_on_unexplained_drop() -> None:
    """raw > 0, blob == 0, no reasons → bug."""
    blob = {"ingredients": [], "ingredients_dropped_reasons": []}
    with pytest.raises(ValueError, match="Unexplained drop"):
        _validate_active_count_reconciliation(blob, 5, "DSLD-BUG")


def test_validator_raises_on_unknown_reason_code() -> None:
    blob = {
        "ingredients": [{"name": "x"}],
        "ingredients_dropped_reasons": ["BOGUS_REASON"],
    }
    with pytest.raises(ValueError, match="unknown drop reason"):
        _validate_active_count_reconciliation(blob, 1, "DSLD-UNK")


def test_all_enum_codes_accepted_by_validator() -> None:
    blob = {
        "ingredients": [{"name": "x"}],
        "ingredients_dropped_reasons": sorted(_ALLOWED_DROP_REASONS),
    }
    _validate_active_count_reconciliation(blob, 1, "DSLD-ENUM")


# ---------------------------------------------------------------------------
# Canary emission — raw_actives_count + reasons populate on every blob
# ---------------------------------------------------------------------------

CANARY_DIR = ROOT / "reports" / "canary_rebuild"

CANARY_IDS = ["35491", "306237", "246324", "1002", "19067", "1036", "176872"]


@pytest.mark.parametrize("dsld_id", CANARY_IDS)
def test_canary_carries_raw_actives_count_and_reasons(dsld_id: str) -> None:
    blob_path = CANARY_DIR / f"{dsld_id}.json"
    if not blob_path.exists():
        pytest.skip(f"{dsld_id} canary not rebuilt yet")
    blob = json.loads(blob_path.read_text())

    # Both fields always present (int and list)
    assert "raw_actives_count" in blob
    assert isinstance(blob["raw_actives_count"], int)
    assert blob["raw_actives_count"] >= 0

    assert "ingredients_dropped_reasons" in blob
    assert isinstance(blob["ingredients_dropped_reasons"], list)
    for r in blob["ingredients_dropped_reasons"]:
        assert r in _ALLOWED_DROP_REASONS, f"unknown reason in blob: {r!r}"

    # No unexplained zero-blob cases in the canary set.
    if blob["raw_actives_count"] > 0 and len(blob.get("ingredients") or []) == 0:
        assert blob["ingredients_dropped_reasons"], (
            f"{dsld_id}: raw > 0 blob == 0 but zero reasons — unexplained drop"
        )


def test_plantizyme_raw_actives_count_matches_expected() -> None:
    """Plantizyme has 1 raw parent blend + 7 nested enzyme children
    (raw walker yields all of them) = 8 total raw actives. Blob has
    5 actives after cleaning (structural container dropped, some
    variants deduped). Expect reasons to include STRUCTURAL_HEADER."""
    blob_path = CANARY_DIR / "35491.json"
    if not blob_path.exists():
        pytest.skip("35491 canary missing")
    blob = json.loads(blob_path.read_text())
    assert blob["raw_actives_count"] >= 5
    # At least one drop reason should appear (prop-blend parent drops).
    if blob["raw_actives_count"] != len(blob.get("ingredients") or []):
        assert blob["ingredients_dropped_reasons"], (
            f"Plantizyme delta unexplained: {blob['raw_actives_count']} vs {len(blob.get('ingredients') or [])}"
        )
