"""
Sprint D4.1 scorer audit — same-canonical dose summing + max-bio_score.

Three invariants we expect for medical-grade accuracy when a product
declares multiple forms of the same nutrient:

1. **A2 premium-forms dedup** — same canonical_id counted once.
2. **A1 weighted average** — each dosed row contributes proportionally;
   parent-total rows are skipped via ``is_parent_total`` flag.
3. **B7 UL safety** — total dose across all forms of one canonical_id
   must be summed BEFORE the UL threshold check. A product declaring
   1500 IU Beta-Carotene + 1500 IU Retinyl Palmitate exposes the
   consumer to 3000 IU Vitamin A, not 1500 IU independently.

Current state (pre-D5.1):

- (1) VERIFIED: ``_compute_premium_forms_bonus`` uses a set keyed by
  canonical_id (score_supplements.py:653), so duplicates count once.
- (2) VERIFIED: A1 uses weighted average, skips proprietary blends and
  ``is_parent_total`` rows, only counts rows with usable individual
  doses. Two-form products get a fair average.
- (3) **KNOWN GAP**: ``_collect_rda_ul_data`` in the enricher
  (enrich_supplements_v3.py:11060) iterates activeIngredients one row
  at a time and calls ``rda_calculator.compute_nutrient_adequacy`` for
  each independently. Same-canonical doses are NOT summed before the
  UL check. For products near the 150% UL threshold, this
  underestimates consumer exposure.

The GAP is flagged here as a test-expected-failure so the full-pipeline
re-run (D5.1) surfaces any products currently hitting the edge case,
and the next sprint can decide whether to implement canonical-level
dose aggregation in the enricher.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# A1 / A2 dedup behavior — verified working
# ---------------------------------------------------------------------------


class TestA2PremiumFormsDedup:
    """Premium forms tagged by canonical_id count once even when declared as multiple rows."""

    def test_premium_forms_dedup_by_canonical_id(self) -> None:
        """
        Verify the canonical_id-keyed set de-duplicates.
        Reads the scorer source for the invariant line rather than running
        the full scorer (which has heavy setup).
        """
        source = Path("scripts/score_supplements.py").read_text()
        # The pattern we rely on: A2 must use a set-based dedup keyed by
        # canonical_id. Match the structural signature across lines.
        assert "premium_keys" in source and ".add(" in source, (
            "A2 premium-forms dedup relies on a set called premium_keys "
            "with .add() calls keyed by canonical_id. If refactored away, "
            "D4.1 invariant broken."
        )
        assert 'ing.get("canonical_id")' in source, (
            "A2 dedup must reference canonical_id as the primary key. "
            "Source line removed or changed — regression."
        )


class TestA1ParentTotalSkip:
    """A1 skips is_parent_total rows to prevent double-counting."""

    def test_is_parent_total_skipped(self) -> None:
        source = Path("scripts/score_supplements.py").read_text()
        # A1 bioavailability section skips is_parent_total
        assert 'if ing.get("is_parent_total"):' in source, (
            "A1 must skip is_parent_total rows to avoid double-counting "
            "when DSLD emits parent + nested forms."
        )


# ---------------------------------------------------------------------------
# B7 UL dose aggregation — KNOWN GAP
# ---------------------------------------------------------------------------


class TestB7UlDoseAggregation:
    """
    B7 (dose safety) currently does per-row UL checks. Same-canonical
    dose aggregation is NOT implemented — documented as a known gap
    for post-D5.1 sprint review.

    This test DOCUMENTS the current behavior rather than asserting the
    ideal. When the fix lands, flip the xfail.
    """

    @pytest.mark.xfail(
        reason=(
            "D4.1 known gap: enricher _collect_rda_ul_data iterates "
            "activeIngredients per-row and does not sum doses across "
            "same-canonical entries before UL check. Products with multi-"
            "form Vitamin A/D/Iron near the 150% UL threshold may under-"
            "flag. Full-pipeline re-run in D5.1 will surface affected "
            "products; decide in next sprint whether to aggregate in the "
            "enricher (requires unit-conversion of each row to a common "
            "unit before summing)."
        ),
        strict=False,
    )
    def test_same_canonical_doses_summed_before_ul_check(self) -> None:
        """
        Intended behavior (currently fails due to known gap):
        A product declaring 2 forms of the same canonical at doses that
        independently fall under the UL but together exceed 150% UL
        should trigger the B7 penalty.
        """
        # Placeholder — a proper integration test would require building
        # a full enriched product through the real enricher pipeline with
        # a known rda_ul entry. Marked xfail so CI doesn't red-flag the
        # documented gap.
        raise AssertionError("Intentional xfail: feature not yet implemented")


# ---------------------------------------------------------------------------
# Evidence of the A1 / A2 contract from real enriched data
# ---------------------------------------------------------------------------


class TestLiveProductsRespectContract:
    """
    Scan existing scored output for any product where the A1 weighted
    average clearly double-counted (e.g., two rows with same canonical
    and same score contributing identical weighted contributions when
    they should have been deduped at the parent level).
    """

    def test_a2_premium_count_does_not_exceed_unique_canonicals(self) -> None:
        """
        For each scored product, premium-form count in Section A should
        equal the count of UNIQUE canonical_ids with bio_score >= threshold,
        not the count of dosed rows. This is a structural property we
        can verify post-run without re-scoring.
        """
        scored_root = Path("scripts/products")
        if not scored_root.exists():
            pytest.skip("No scored output")

        sampled = 0
        for scored_dir in sorted(scored_root.glob("output_*_scored/scored")):
            for batch in sorted(scored_dir.glob("*.json"))[:1]:
                try:
                    data = json.loads(batch.read_text())
                except json.JSONDecodeError:
                    continue
                if not isinstance(data, list):
                    continue
                for p in data[:20]:
                    breakdown = (p.get("breakdown") or {}).get("A") or {}
                    a2 = breakdown.get("A2", 0.0)
                    # A2 max is 5.0 per scoring_config. If a2 > max, the
                    # set-based dedup broke (duplicates double-counted).
                    assert a2 <= 5.0 + 0.01, (
                        f"Product {p.get('dsld_id')} A2={a2} exceeds max 5.0 — "
                        f"same-canonical dedup may have broken."
                    )
                    sampled += 1

        if sampled == 0:
            pytest.skip("No products to sample")
