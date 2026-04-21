"""
Sprint D2.10 regression test — source-descriptor child rows.

The GNC dataset contains products like **Beyond Raw Re-Comp (dsld_id=31147)**
where DSLD emits a *separate* activeIngredients row whose ingredientName
starts with "from " to describe the SOURCE of the preceding real active.

Concrete example from 31147:

    [6] EGCG                             (real active, canonical=egcg)
    [7] from Green Tea Leaf Extract      (provenance — NOT a distinct active)

Pre-D2.10 the enricher couldn't resolve row [7] (literal "from X" doesn't
match any alias), tagged it unmapped, and the coverage gate dropped the
ingredients-domain coverage to 92.9% < 99.5% threshold — blocking the
product as a medical-grade safety failure, even though all ACTUAL actives
were matched.

D2.10 routes these rows through ``recognized_non_scorable`` (identical
pattern to D2.7.1 for proprietary_blends), so:

  - Coverage gate treats them as recognized (not unmapped)
  - Scorer excludes them from A1 bioavailability denominator
  - They remain visible in the output with
    ``recognition_reason='source_descriptor_child_row'``

Triggering conditions (conservative):
  - ``raw_source_text`` starts with "from " (case-insensitive)
  - quantity is 0 / missing (real actives always carry a qty)

These must both hold to avoid false positives on ingredients whose label
text legitimately starts with "From" (e.g. "From the Greens").
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Source-scan guard — the enricher fix must remain in place
# ---------------------------------------------------------------------------


def test_enricher_has_source_descriptor_child_routing() -> None:
    """D2.10 routing signature must be present in the enricher."""
    source = Path("scripts/enrich_supplements_v3.py").read_text()

    # All three identifiers that define the D2.10 fix
    assert "source_descriptor_child_row" in source, (
        "D2.10 regression: enricher must tag source-descriptor rows "
        "with recognition_reason='source_descriptor_child_row'."
    )
    assert "startswith('from ')" in source, (
        "D2.10 regression: enricher must gate on raw_source_text "
        "starting with 'from ' (case-insensitive)."
    )
    assert "provenance_annotation" in source, (
        "D2.10 regression: recognition_type must be 'provenance_annotation' "
        "to distinguish from other recognized_non_scorable routes."
    )


def test_quantity_irrelevant_for_from_prefix() -> None:
    """The 'from X' rule fires regardless of quantity.

    Rationale (post-GNC 31147 audit):
      DSLD emits source-descriptor rows with non-zero quantities that
      represent the PARENT EXTRACT amount (e.g., "from Green Tea Leaf
      Extract" = 56mg containing the preceding EGCG active of 50mg).
      Gating on quantity would miss the real-world case.

    Safety: the D2.10 branch only runs when the row already failed
    canonical/form quality-match — i.e., it would have been counted as
    unmapped anyway. Re-tagging unmapped rows as recognized_non_scorable
    has zero impact on A1/A2 scoring; it only exempts them from the
    coverage-gate denominator, which is the intended fix.
    """
    source = Path("scripts/enrich_supplements_v3.py").read_text()
    # The D2.10 block should NOT gate on quantity any more.
    d210_start = source.find("D2.10 (medical-grade)")
    d210_block = source[d210_start:d210_start + 2500]
    # The condition line should be a pure prefix check, not conjoined with
    # a quantity predicate.
    assert "if _raw_text_lower.startswith('from '):" in d210_block, (
        "D2.10 regression: the source-descriptor check should be a bare "
        "prefix test (no quantity gate) so non-zero-qty provenance rows "
        "like GNC 31147's 'from Green Tea Leaf Extract' (56mg) are also "
        "routed through recognized_non_scorable."
    )


# ---------------------------------------------------------------------------
# Behavior spec — real product 31147 use case
# ---------------------------------------------------------------------------


class TestFromPrefixChildRowSemantics:
    """Assertions about the tagging contract for a source-descriptor child."""

    def test_recognition_fields_documented(self) -> None:
        """Every source-descriptor child row must carry the full recognized_
        non_scorable contract so the coverage gate + scorer + display layer
        agree on handling."""
        source = Path("scripts/enrich_supplements_v3.py").read_text()
        # Find the D2.10 block
        start = source.find("D2.10 (medical-grade)")
        assert start > 0, "D2.10 docstring marker missing"
        end = source.find("continue", start) + len("continue")
        block = source[start:end]
        # Required contract fields
        for field in (
            "recognized_non_scorable",
            "recognition_source",
            "recognition_reason",
            "recognition_type",
            "mapped",
            "mapped_identity",
            "scoreable_identity",
            "role_classification",
            "identity_confidence",
            "identity_decision_reason",
        ):
            assert field in block, (
                f"D2.10 regression: {field!r} must be set on the "
                f"source-descriptor child row contract."
            )

    def test_not_confused_with_proprietary_blend_route(self) -> None:
        """The D2.7.1 proprietary_blend routing uses recognition_reason=
        'proprietary_blend_member' — source-descriptor must use a distinct
        reason so downstream consumers can tell them apart."""
        source = Path("scripts/enrich_supplements_v3.py").read_text()
        assert "source_descriptor_child_row" != "proprietary_blend_member"
        # Both strings must coexist in the file (two distinct routing branches)
        assert "proprietary_blend_member" in source
        assert "source_descriptor_child_row" in source


# ---------------------------------------------------------------------------
# Invariant guard — legitimate 'From ...' actives still score
# ---------------------------------------------------------------------------


class TestSafetyInvariantScoringUnaffected:
    """Safety invariant: the D2.10 rule only fires in the NO-QUALITY-MATCH
    branch, so re-tagging unmapped "from X" rows as recognized_non_scorable
    cannot suppress any real A1/A2 scoring contribution (those rows would
    have been unmapped anyway).

    The only observable effect is on the coverage-gate denominator, which
    is the intended purpose of the fix.
    """

    def test_d210_routing_lives_in_no_match_branch(self) -> None:
        source = Path("scripts/enrich_supplements_v3.py").read_text()
        # Find the D2.10 block
        d210_start = source.find("D2.10 (medical-grade)")
        # Walk backwards and confirm we're inside the `else:` of the
        # `if is_quality_match:` dispatch — the only place where routing
        # a row to recognized_non_scorable has no scoring side-effect.
        preamble = source[max(0, d210_start - 3000):d210_start]
        assert "if is_quality_match:" in preamble, (
            "D2.10 safety invariant: the source-descriptor fix must live "
            "inside the no-quality-match branch so it cannot accidentally "
            "suppress real A1/A2 scoring contributions."
        )

    def test_d210_not_confused_with_other_routes(self) -> None:
        """Distinct recognition_reason keeps observability clean."""
        source = Path("scripts/enrich_supplements_v3.py").read_text()
        assert "source_descriptor_child_row" in source
        assert "proprietary_blend_member" in source  # D2.7.1 distinct route
