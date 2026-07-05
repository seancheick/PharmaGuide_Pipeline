"""
Review follow-up — don't ship the V3-basis "Top X%" percentile next to a V4 score.

`category_percentile` is frozen at score time by
score_supplements._attach_category_percentiles, which ranks on
`score_100_equivalent` (= the retired V3 score). export_adapter later overwrites
the score with the V4 value but never recomputes the percentile, so the badge is
ranked by a different model than the score shown. Until a V4 percentile is
recomputed at build time, suppress the rank (hide) rather than mislead.
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
        "V3-basis percentile_rank must not ship next to a V4 score"
    )
    assert row["percentile_top_pct"] is None, (
        "V3-basis percentile_top_pct must not ship next to a V4 score"
    )
