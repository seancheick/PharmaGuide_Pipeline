#!/usr/bin/env python3
"""Flutter pickup smoke test — pins the 9 new RECALLED_ entries from the
2026-05-13 → 2026-05-14 sweep to the inactive_ingredient_resolver.

What this test guarantees (for each of the 9 entries):
  1. Resolver matches by canonical product name → returns
     SOURCE_BANNED_RECALLED with the expected rule_id.
  2. severity_status = SEVERITY_CRITICAL.
  3. is_safety_concern = True.
  4. is_banned = False  (all 9 are RECALLED, not BANNED — distinction matters
     for Flutter's red-banner copy).
  5. safety_reason is populated (resolver pulls it from
     `safety_warning_one_liner`; ≥20 chars to weed out empty strings).
  6. safety_warning is populated (the Dr Pham authored paragraph; ≥50 chars).
  7. references list is non-empty (FDA enforcement-report URLs).
  8. identifiers includes external_ids (UNII codes, FDA recall IDs).

These collectively prove the full path:
    JSON entry → resolver → Flutter blob payload
is intact for the entries added/reauthored in this sweep.

This was authored after the 2026-05-14 reauthoring pass uncovered two
alias gaps (Divided Sunset / Boner Bears) that prevented Flutter pickup.
Both fixed at the time of authoring this test; the test pins them so the
same regression cannot recur.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from inactive_ingredient_resolver import (  # noqa: E402
    InactiveIngredientResolver,
    SEVERITY_CRITICAL,
    SOURCE_BANNED_RECALLED,
)

# (raw_name as a Flutter user might see on a label, expected_rule_id)
NEW_RECALL_CASES = [
    ("SiluetaYa Mexican Tejocote Roots", "RECALLED_SILUETAYA_TEJOCOTE"),
    ("Aonic Complete HERS", "RECALLED_AONIC_COMPLETE_HERS"),
    ("Aonic Complete HIS", "RECALLED_AONIC_COMPLETE_HIS"),
    ("Imu-Tek Colostrum-5 Capsules", "RECALLED_IMU_TEK_COLOSTRUM_5_CAPSULES"),
    ("Imu-Tek Colostrum-5 Powder", "RECALLED_IMU_TEK_COLOSTRUM_5_POWDER"),
    ("Divided Sunset Collagen Peptides",
     "RECALLED_DIVIDED_SUNSET_COLLAGEN_PEPTIDES"),
    ("Blue Bull Extreme", "RECALLED_BLUE_BULL_EXTREME"),
    ("Red Bull Extreme", "RECALLED_RED_BULL_EXTREME"),
    ("Boner Bears Honey", "RECALLED_BONER_BEARS_HONEY"),
]


@pytest.fixture(scope="module")
def resolver() -> InactiveIngredientResolver:
    data = REPO_ROOT / "scripts" / "data"
    return InactiveIngredientResolver(
        banned_recalled_path=data / "banned_recalled_ingredients.json",
        harmful_additives_path=data / "harmful_additives.json",
        other_ingredients_path=data / "other_ingredients.json",
    )


@pytest.mark.parametrize("raw_name,expected_id", NEW_RECALL_CASES,
                         ids=[c[1] for c in NEW_RECALL_CASES])
def test_new_recalled_entry_resolves_with_flutter_payload(
    resolver: InactiveIngredientResolver,
    raw_name: str,
    expected_id: str,
) -> None:
    """Each 2026-05 RECALLED_ entry must resolve with the full payload
    Flutter consumes from inactive_ingredient_resolver._from_banned."""
    res = resolver.resolve(raw_name)

    assert res.matched_source == SOURCE_BANNED_RECALLED, (
        f"{expected_id}: resolver did not match {raw_name!r} to banned_recalled "
        f"(got matched_source={res.matched_source!r}). "
        "Likely an alias gap — add an alias for this surface form."
    )
    assert res.matched_rule_id == expected_id, (
        f"matched the wrong entry: got {res.matched_rule_id!r}, "
        f"expected {expected_id!r}"
    )
    assert res.severity_status == SEVERITY_CRITICAL, (
        f"{expected_id}: severity must be CRITICAL for recalled status"
    )
    assert res.is_safety_concern is True, (
        f"{expected_id}: is_safety_concern must be True"
    )
    assert res.is_banned is False, (
        f"{expected_id}: status=recalled must NOT set is_banned=True"
    )
    # safety_reason flows from safety_warning_one_liner (short copy).
    assert res.safety_reason and len(res.safety_reason) >= 20, (
        f"{expected_id}: safety_reason missing or too short"
    )
    # safety_warning is the full Dr Pham paragraph.
    assert res.safety_warning and len(res.safety_warning) >= 50, (
        f"{expected_id}: safety_warning missing or too short"
    )
    # references_structured threads through to references.
    assert len(res.references or []) >= 1, (
        f"{expected_id}: at least one FDA reference must be threaded through"
    )
    # external_ids (UNII codes, FDA recall IDs) reaches Flutter via
    # identifiers — this is what powers the "why was this flagged" link card.
    assert "external_ids" in res.identifiers, (
        f"{expected_id}: identifiers must include external_ids"
    )
    assert res.identifiers["external_ids"], (
        f"{expected_id}: external_ids must be non-empty"
    )


def test_smoke_count_pins_all_nine_entries() -> None:
    """Guard: if the sweep added/removed entries, this list must change
    deliberately rather than drift."""
    assert len(NEW_RECALL_CASES) == 9, (
        "Test pins the 9 RECALLED_ entries from the 2026-05-13 sweep. "
        "If the count changed, update NEW_RECALL_CASES explicitly."
    )
