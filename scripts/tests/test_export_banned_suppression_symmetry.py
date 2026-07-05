"""
P0-3 regression — v4 banned-suppression symmetry at export.

Bug: ``build_final_db`` suppresses the v4 public score only on the NARROW
``has_banned_substance(enriched)`` signal (build_final_db.py ~8322), but the
export hard-blocks on the BROADER ``has_export_banned_signal`` =
``has_banned_substance(...) OR blob_has_critical_banned_warning(detail_blob)``
(build_final_db.py:7749). The 7754 branch nulls the legacy score_100_equivalent
but leaves ``_v4_quality_score_100`` / ``_v4_quality_status`` from the overlay.

Result: a product blocked ONLY via a resolver-detected inactive ban (the
titanium-dioxide class — caught by the blob critical warning, missed by
``has_banned_substance``) ships ``verdict=BLOCKED`` yet keeps a finite,
rankable ``quality_score_v4_100`` with ``quality_score_status='scored'`` — so it
stays in ``idx_core_cat_score`` (WHERE status='scored') and can win UPC dedup by
``COALESCE(quality_score_v4_100, …)``. A hard-blocked product must never carry a
rankable consumer score.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))          # scripts/tests (helpers)
sys.path.insert(0, str(Path(__file__).parent.parent))   # scripts

from build_final_db import build_core_row, has_banned_substance
from test_build_final_db import make_scored, make_enriched, row_as_dict


def test_export_banned_via_blob_warning_suppresses_v4_score() -> None:
    enriched = make_enriched()
    # Precondition: the fixture is NOT banned via has_banned_substance — the
    # ban signal here comes ONLY from the blob critical-warning path.
    assert has_banned_substance(enriched) is False

    # Post-overlay, pre-suppress state: v4 produced a finite score/status.
    scored = make_scored(verdict="SAFE")
    scored["_v4_quality_score_100"] = 72.0
    scored["_v4_quality_status"] = "scored"
    scored["_v4_quality_tier"] = "Good"
    scored["_v4_raw_score_100"] = 72.0

    # Detail blob carrying a critical banned-substance warning (e.g. a
    # resolver-detected inactive ban like titanium dioxide) — the broader
    # export ban signal that has_banned_substance misses.
    blob = {
        "warnings": [
            {"type": "banned_substance", "severity": "critical", "ingredient": "Titanium Dioxide"}
        ]
    }

    row = row_as_dict(
        build_core_row(enriched, scored, "2026-07-05T00:00:00Z", detail_blob=blob)
    )

    # The export hard-blocks the product ...
    assert row["verdict"] == "BLOCKED"
    # ... so the v4 public contract MUST be suppressed to match — a BLOCKED
    # product cannot ship a finite, rankable quality_score_v4_100.
    assert row["quality_score_v4_100"] is None, (
        f"BLOCKED product shipped a rankable v4 score: {row['quality_score_v4_100']}"
    )
    assert row["quality_score_status"] != "scored", (
        f"BLOCKED product ships quality_score_status={row['quality_score_status']!r} "
        f"(must not be 'scored' — it would stay in idx_core_cat_score)"
    )


def test_non_banned_product_keeps_its_v4_score() -> None:
    """Guard: a clean product with no ban signal keeps its finite v4 score."""
    enriched = make_enriched()
    assert has_banned_substance(enriched) is False

    scored = make_scored(verdict="SAFE")
    scored["_v4_quality_score_100"] = 72.0
    scored["_v4_quality_status"] = "scored"

    row = row_as_dict(build_core_row(enriched, scored, "2026-07-05T00:00:00Z"))

    assert row["quality_score_v4_100"] == 72.0
    assert row["quality_score_status"] == "scored"
