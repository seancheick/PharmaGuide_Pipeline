"""SP-2 adoption regression test — locks the inventory of legacy-classification
reads in the v4 + v4 scorer + build_final_db surface.

Source: `scripts/audits/sp2_adoption_audit.py` enumerates every line that
reads `supplement_type`, `primary_category`, or `category_breakdown` in the
SP-2 scoped files (see `scripts/audits/sp2_adoption/INVENTORY.md`).

This test fails when:
  - A new legacy-classification read is added to ANY scoped file without
    updating the expected baseline below.
  - A migration lands and the count drops — that's good news; update the
    baseline to lock the new lower number.

Design rationale (Sean's central constraint from the SP-0 design doc):
  > Downstream stages may use legacy fields only when the normalized
  > taxonomy is absent in old batches. Name-keyword fallbacks must be
  > local, documented, and guarded by canary tests because they are
  > less reliable than normalized IDs.

The baseline counts below represent the current state. Each MIGRATE
target listed in INVENTORY.md will reduce the count for its file when
the migration commit lands.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "audits"))

from sp2_adoption_audit import enumerate_sp2_legacy_reads, hits_grouped_by_file


# Baseline per-file legacy read counts. Updated atomically when migrations land.
# See INVENTORY.md for the verdict on each hit.
#
# Counts reflect REAL code reads only — the audit script skips docstring
# text and comments. Files with 0 hits are omitted from
# hits_grouped_by_file().
#
# Migration plan (each commit lands an atomic decrease):
#   T3 ADOPT-3: generic_trust.py 1 -> 0 (supp_type=specialty branch removed)
#   T5 ADOPT-1: confidence.py 1 -> 1 (additive — taxonomy driver added,
#                legacy supp.confidence kept as fallback for old batches)
#   T6 ADOPT-2: generic_helpers.py 1 -> 1 (additive — `primary_type_of()`
#                helper added; `supp_type_of()` preserved for callers)
#   T4 ADOPT-4: generic_transparency.py 4 -> 0 (parallel classifier
#                replaced with `router.class_for_product` delegation +
#                sports overlay)
EXPECTED_HITS_PER_FILE = {
    "scripts/build_final_db.py": 15,
    "scripts/scoring_v4/confidence.py": 1,
    "scripts/scoring_v4/modules/generic_helpers.py": 1,
    "scripts/scoring_v4/router.py": 1,
}


def test_sp2_scoped_files_have_expected_legacy_read_counts():
    """Lock the inventory baseline. Increase = regression; decrease = unlock
    by updating EXPECTED_HITS_PER_FILE.
    """
    actual = {file: len(hits) for file, hits in hits_grouped_by_file().items()}

    # Files we expect to see in the inventory
    expected_files = set(EXPECTED_HITS_PER_FILE.keys())
    actual_files = set(actual.keys())

    new_files = actual_files - expected_files
    assert not new_files, (
        f"New file appeared in SP-2 scoped inventory: {new_files}. "
        f"Either migrate to taxonomy or document the legacy read in INVENTORY.md "
        f"and add to EXPECTED_HITS_PER_FILE."
    )

    diffs = []
    for file, expected_count in EXPECTED_HITS_PER_FILE.items():
        actual_count = actual.get(file, 0)
        if actual_count > expected_count:
            diffs.append(
                f"  {file}: expected {expected_count}, got {actual_count} "
                f"(+{actual_count - expected_count} new legacy reads)"
            )
        elif actual_count < expected_count:
            diffs.append(
                f"  {file}: expected {expected_count}, got {actual_count} "
                f"({expected_count - actual_count} migrated — update baseline)"
            )

    assert not diffs, (
        "SP-2 adoption inventory drift detected:\n" + "\n".join(diffs) +
        "\n\nIf this is a new legacy read: classify it in INVENTORY.md first.\n"
        "If this is a migration: update EXPECTED_HITS_PER_FILE to the new lower count."
    )


def test_sp2_total_legacy_reads_locked():
    """Total count safety net — catches drift even if per-file shifts cancel out."""
    total = len(enumerate_sp2_legacy_reads())
    expected = sum(EXPECTED_HITS_PER_FILE.values())
    assert total == expected, (
        f"Total legacy reads in SP-2 scope: expected {expected}, got {total}. "
        f"Update per-file baselines in EXPECTED_HITS_PER_FILE after migration."
    )


def test_sp2_inventory_doc_exists():
    """INVENTORY.md must exist alongside the audit script."""
    import pathlib
    inventory = pathlib.Path(__file__).resolve().parents[1] / "audits" / "sp2_adoption" / "INVENTORY.md"
    assert inventory.is_file(), (
        f"SP-2 inventory doc missing: {inventory}. "
        f"Every adoption migration must keep the inventory in sync."
    )


def test_sp2_router_legacy_read_is_only_themed_multi_broad_panel_fallback():
    """The router reads taxonomy first. Its only legacy read is the explicitly
    guarded themed-multivitamin fallback, which also requires broad-panel
    physical evidence."""
    import pathlib
    router = pathlib.Path(__file__).resolve().parents[1] / "scoring_v4" / "router.py"
    src = router.read_text()
    primary_type_idx = src.find("_read_primary_type(product)")
    assert primary_type_idx != -1, "Router must call _read_primary_type"
    assert "_read_legacy_supp_type(product)" not in src
    assert src.count('get("supplement_type")') == 1
    assert "_has_broad_legacy_multivitamin_panel" in src
    assert 'get("primary_category")' not in src


def test_sp2_shadow_scorer_delegates_to_router():
    """The v4 scorer must use router.class_for_product, not its own
    classification logic."""
    import pathlib
    shadow = pathlib.Path(__file__).resolve().parents[1] / "score_supplements_v4.py"
    src = shadow.read_text()
    assert "from scoring_v4.router import class_for_product" in src, (
        "Shadow scorer must import class_for_product from the router."
    )
    # Verify no local parallel classifier
    forbidden = (
        "def _class_for_product",
        "def _classify_supplement_type",
        "def _b5_class_for_product",
    )
    for symbol in forbidden:
        assert symbol not in src, (
            f"Shadow scorer must NOT define {symbol!r} — that would create a "
            f"parallel classifier. Use router.class_for_product instead."
        )
