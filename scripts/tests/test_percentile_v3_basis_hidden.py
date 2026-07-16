"""
Review follow-up — don't ship the V3-basis "Top X%" percentile next to a V4 score.

`category_percentile` is frozen at score time by
the retired scorer's percentile path, which ranked on its own
`score_100_equivalent`. The v4-native artifact now owns that compatibility
field, but old on-disk artifacts can still carry a percentile frozen under the
retired model. That rank must not be paired with the v4 score shown.

build_core_row must therefore emit percentile_rank / top_pct / cohort as NULL —
the shippable V4 percentile is BACKFILLED after the insert loop by
compute_v4_category_percentiles (ranked over quality_score_v4_100 across the
surviving cohort). This test guards the per-row emitter: it must never leak the
frozen V3-basis rank/cohort, or the backfill would be racing a stale value.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from build_final_db import build_core_row
from test_build_final_db import make_scored, make_enriched, row_as_dict


def test_v3_basis_percentile_rank_is_suppressed():
    enriched = make_enriched()
    scored = make_scored(verdict="SAFE")  # carries category_percentile rank=90, top=10
    scored["_v4_quality_score_100"] = 72.0
    scored["_v4_quality_status"] = "scored"

    row = row_as_dict(build_core_row(enriched, scored, "2026-07-05T00:00:00Z"))

    assert row["percentile_rank"] is None, (
        "V3-basis percentile_rank must not ship from build_core_row (backfilled)"
    )
    assert row["percentile_top_pct"] is None, (
        "V3-basis percentile_top_pct must not ship from build_core_row (backfilled)"
    )
    assert row["percentile_cohort"] is None, (
        "V3-basis percentile_cohort must not ship from build_core_row (backfilled)"
    )
