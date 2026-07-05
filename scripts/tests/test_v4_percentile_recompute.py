"""V4 category-percentile recompute (build_final_db).

score_supplements._attach_category_percentiles ranks products on the retired V3
score_100_equivalent and freezes the result at score time. The export overwrites
the shipped score with the v4 /100 value but never re-ranks, so the badge would
be ranked by a different model than the score shown. build_final_db recomputes
the percentile over the actually-shipped quality_score_v4_100 cohort.

These tests lock the recompute to the SAME arithmetic as the V3 implementation:
    higher = count strictly greater
    equal  = count equal (incl. self)
    rank   = higher + (equal + 1) / 2
    top%   = clamp(0, 100, rank / cohort_size * 100), 1dp
    prank  = 100 - top%
    cohort < min_cohort (5) -> unranked (no row emitted; columns stay NULL)
"""

import pytest

from build_final_db import compute_v4_category_percentiles


def _by_pid(updates):
    # updates are (percentile_rank, top_pct, cohort_size, dsld_id)
    return {u[3]: u for u in updates}


class TestV4PercentileRecompute:
    def test_ranks_within_category_cohort(self):
        rows = [
            ("a1", "cat_a", 90.0),
            ("a2", "cat_a", 80.0),
            ("a3", "cat_a", 70.0),
            ("a4", "cat_a", 60.0),
            ("a5", "cat_a", 50.0),
        ]
        out = _by_pid(compute_v4_category_percentiles(rows, min_cohort=5))

        # equal_count includes the product itself, so the minimum rank is 1.0.
        # Top scorer: higher=0, equal=1 -> rank=1.0 -> top%=20.0 -> prank=80.0
        assert out["a1"] == (80.0, 20.0, 5, "a1")
        # Bottom scorer: higher=4, equal=1 -> rank=5.0 -> top%=100.0 -> prank=0.0
        assert out["a5"] == (0.0, 100.0, 5, "a5")
        # Median scorer: higher=2, equal=1 -> rank=3.0 -> top%=60.0 -> prank=40.0
        assert out["a3"] == (40.0, 60.0, 5, "a3")

    def test_all_ties_share_the_midpoint(self):
        rows = [(f"t{i}", "cat_tie", 88.0) for i in range(5)]
        out = _by_pid(compute_v4_category_percentiles(rows, min_cohort=5))
        # higher=0, equal=5 -> rank=(5+1)/2=3.0 -> top%=60.0 -> prank=40.0
        for i in range(5):
            assert out[f"t{i}"] == (40.0, 60.0, 5, f"t{i}")

    def test_small_cohort_is_unranked(self):
        rows = [
            ("s1", "cat_small", 100.0),
            ("s2", "cat_small", 90.0),
            ("b1", "cat_big", 90.0),
            ("b2", "cat_big", 80.0),
            ("b3", "cat_big", 70.0),
            ("b4", "cat_big", 60.0),
            ("b5", "cat_big", 50.0),
        ]
        out = _by_pid(compute_v4_category_percentiles(rows, min_cohort=5))
        # cat_small has 2 -> excluded entirely
        assert "s1" not in out and "s2" not in out
        # cat_big has 5 -> ranked
        assert out["b1"][2] == 5
        assert len(out) == 5

    def test_cohorts_are_independent(self):
        rows = [
            ("a1", "cat_a", 99.0),  # top of a small-value cohort
            ("a2", "cat_a", 10.0),
            ("a3", "cat_a", 10.0),
            ("a4", "cat_a", 10.0),
            ("a5", "cat_a", 10.0),
            ("z1", "cat_z", 50.0),  # mid of another cohort
            ("z2", "cat_z", 50.0),
            ("z3", "cat_z", 50.0),
            ("z4", "cat_z", 50.0),
            ("z5", "cat_z", 50.0),
        ]
        out = _by_pid(compute_v4_category_percentiles(rows, min_cohort=5))
        # a1 is the sole top: higher=0, equal=1 -> rank=1.0 -> top%=20.0
        assert out["a1"][:3] == (80.0, 20.0, 5)
        # cat_z is a 5-way tie, independent of cat_a: prank=40.0, top%=60.0
        assert out["z1"][:3] == (40.0, 60.0, 5)

    def test_empty_and_missing_category_ignored(self):
        rows = [
            ("n1", None, 90.0),
            ("n2", "", 80.0),
            ("b1", "cat_big", 90.0),
            ("b2", "cat_big", 80.0),
            ("b3", "cat_big", 70.0),
            ("b4", "cat_big", 60.0),
            ("b5", "cat_big", 50.0),
        ]
        out = _by_pid(compute_v4_category_percentiles(rows, min_cohort=5))
        assert "n1" not in out and "n2" not in out
        assert len(out) == 5
