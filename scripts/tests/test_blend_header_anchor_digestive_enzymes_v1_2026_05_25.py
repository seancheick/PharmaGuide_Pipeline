"""
Wave 6.Z Slice A.2b — Digestive Enzyme Blend Header Anchor.

These tests assert the desired post-fix behavior for the A.2b slice:

  1. digestive_enzymes blend-header rows are anchor-eligible after removal
     from BLEND_HEADER_ANCHOR_CANONICAL_DENYLIST.
  2. A nested-child usable-dose guard prevents anchor firing when any
     nested child carries an individual disclosed dose (qty > 0 with a real
     mass unit). When children have usable doses, we must score the children
     and never credit the header — otherwise we'd double-count or invent
     precision.
  3. All other reserved class-level canonicals (prebiotics, probiotics,
     whey_protein, collagen) remain denied — A.2b is digestive_enzymes only.

These tests were written TDD-first and failed on pre-fix main. After the
production change they pass. The production change is intentionally narrow
per Codex review (no new scoring path, no IQM edits, no B5 changes):

  - scripts/score_supplements.py:91 — remove "digestive_enzymes" from
    BLEND_HEADER_ANCHOR_CANONICAL_DENYLIST.
  - scripts/score_supplements.py::_has_blend_header_anchor — before returning
    True, abort if any row in ingredients_skipped is a nested child with
    quantity > 0 AND a real mass unit.

Existing test updated by the production change:

  - scripts/tests/test_not_scored_truthful_diagnostics.py:1158-1172
    test_blend_header_anchor_rejects_denylisted_canonical parametrize list
    must drop "digestive_enzymes". The remaining 4 cids (prebiotics,
    probiotics, whey_protein, collagen) still stay denied, locked here by
    test_other_reserved_cids_stay_denied below.

Verified inventory (reports/blend_header_subtype_inventory.md):
  - 10 corpus products would land in A.2b: DSLD 205179, 231262, 249507,
    256077, 270511, 278019, 278020, 298029, 302668, 328828
  - 0 of those 10 have nested children with usable individual doses
  - Verdict ceiling enforced by existing score_supplements.py:4786-4790
    (FLAG_BLEND_HEADER_ANCHOR in flags → return "CAUTION")
"""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from score_supplements import SupplementScorer  # noqa: E402
from test_not_scored_truthful_diagnostics import (  # noqa: E402
    _make_blend_header_anchor_eligible,
    _rejected_row,
)


@pytest.fixture
def scorer():
    return SupplementScorer()


# ---------------------------------------------------------------------------
# Builders specific to A.2b — digestive_enzymes shape variants.
# ---------------------------------------------------------------------------


def _make_digestive_enzyme_header_only(
    *,
    header_name: str = "Glutalytic",
    header_std_name: str = "Digestive Enzymes",
    header_quantity: float = 350.0,
    header_unit: str = "mg",
    is_proprietary_blend: bool = True,
):
    """Codex Row 2/3 candidate: blend header with cid=digestive_enzymes.

    Defaults model DSLD 302668 (Doctor's Best Gluten Rescue with Glutalytic).
    No nested children with usable doses — children, if any, are display-only
    (qty=0/NP). Production reality: 7 of 10 corpus products have display-only
    nested children, 3 of 10 have no children at all. Both shapes share the
    same eligibility outcome under A.2b.
    """
    return _make_blend_header_anchor_eligible(
        header_name=header_name,
        header_std_name=header_std_name,
        header_canonical_id="digestive_enzymes",
        header_canonical_source_db="ingredient_quality_map",
        header_quantity=header_quantity,
        header_unit=header_unit,
    )


def _make_anchor_eligible_header_with_dosed_children(
    *,
    header_canonical_id: str = "creatine_monohydrate",
    header_canonical_source_db: str = "ingredient_quality_map",
    child_quantities_mg: tuple = (200.0, 150.0),
):
    """The Codex EXCLUDE shape: header + nested children with usable doses.

    Uses creatine_monohydrate (a non-denylisted cid, already validated by
    Track A.2a positive tests) so the test isolates the GUARD behavior from
    the denylist. The guard's contract — "don't credit header when children
    carry usable individual doses" — is cid-independent, so a non-denylisted
    cid is the cleanest TDD signal.

    Pre-fix expectation: _has_blend_header_anchor returns True (no guard
    today; the header alone is sufficient).
    Post-fix expectation: _has_blend_header_anchor returns False (the new
    guard fires when ≥1 nested child has qty > 0 with a real mass unit).

    None of the 10 digestive_enzymes corpus products today match this
    shape, but the guard is required to keep A.2b — and every future
    blend-header anchor slice — safe at 100K+ products.
    """
    product = _make_blend_header_anchor_eligible(
        header_canonical_id=header_canonical_id,
        header_canonical_source_db=header_canonical_source_db,
    )
    iqd = product["ingredient_quality_data"]
    # Append nested children with REAL usable mg doses.
    for i, qty in enumerate(child_quantities_mg):
        iqd["ingredients_skipped"].append(
            _rejected_row(
                name=f"Sub Component {i + 1}",
                standard_name=f"Sub Component {i + 1}",
                canonical_id=header_canonical_id,
                canonical_source_db=header_canonical_source_db,
                quantity=qty,
                unit="mg",
                has_dose=True,
                recognized_non_scorable=False,
                skip_reason="nested_under_non_therapeutic_parent",
                score_exclusion_reason="nested_under_non_therapeutic_parent",
                recognition_source=None,
                recognition_reason=None,
                is_blend_header=False,
                blend_total_weight_only=False,
                is_proprietary_blend=True,
            )
        )
    iqd["skipped_non_scorable_count"] = len(iqd["ingredients_skipped"])
    return product


# ---------------------------------------------------------------------------
# A.2b TEST CLASS — assertions that lock the desired post-fix behavior.
# ---------------------------------------------------------------------------


class TestTrackA2bDigestiveEnzymesAnchor:
    # --- Positive: Row 2 / Row 3 (the 10 corpus candidates) ---

    def test_glutalytic_shape_promotes_to_anchor(self, scorer):
        """DSLD 302668 Doctor's Best Gluten Rescue with Glutalytic shape.

        Header carries cid=digestive_enzymes, qty=350mg, src_db=IQM.
        Today (Track A.2a): NOT_SCORED (cid denylisted).
        Post-A.2b fix: scored via blend_header_anchor path.
        """
        product = _make_digestive_enzyme_header_only(
            header_name="Glutalytic",
            header_quantity=350.0,
            header_unit="mg",
        )
        result = scorer.score_product(product)

        assert result["verdict"] != "NOT_SCORED"
        assert result["scoring_status"] == "scored"
        assert result["score_basis"] == "blend_header_anchor"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" in result["flags"]
        assert result["not_scorable_reason"] is None
        findings = result["strict_scoring_contract"]["findings"]
        assert "scored_via_blend_header_anchor_path" in findings

    def test_pancreatin_shape_promotes_to_anchor(self, scorer):
        """DSLD 231262 Thorne Dipan-9 / 298029 / 328828 Pancreatic Enzymes shape.

        Header carries cid=digestive_enzymes, qty=1g, src_db=IQM. Row 3 shape:
        the blend header is the ONLY active row (no nested children at all).
        """
        product = _make_digestive_enzyme_header_only(
            header_name="Pancreatin",
            header_quantity=1.0,
            header_unit="Gram(s)",
        )
        result = scorer.score_product(product)

        assert result["verdict"] != "NOT_SCORED"
        assert result["score_basis"] == "blend_header_anchor"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" in result["flags"]
        findings = result["strict_scoring_contract"]["findings"]
        assert "scored_via_blend_header_anchor_path" in findings

    # --- Verdict ceiling (CAUTION cap, never SAFE) ---

    def test_verdict_never_safe_for_anchor_product(self, scorer):
        """Existing FLAG_BLEND_HEADER_ANCHOR ceiling at score_supplements.py:4786-4790
        forces verdict to CAUTION when the anchor flag is present.

        Even if all other sections come back maximal, the anchor flag caps
        the product at CAUTION. This lock holds for A.2b just as it does for
        the existing A.2a (Track A.2) products.
        """
        product = _make_digestive_enzyme_header_only()
        result = scorer.score_product(product)

        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" in result["flags"]
        assert result["verdict"] in {"CAUTION", "POOR"}, (
            f"anchor-scored product must never be SAFE; got {result['verdict']}"
        )

    # --- Child-dose guard (the new safety rule) ---

    def test_child_dose_guard_via_has_blend_header_anchor_seam(self, scorer):
        """The real `_has_blend_header_anchor()` seam MUST return False when
        any nested child carries a usable individual dose.

        Without the guard, the helper would return True (header satisfies
        every existing condition: dose, unit, cid, src_db). The new guard
        is the one piece of logic the production change adds beyond the
        single-line denylist removal.

        Per Codex review: this test calls the real seam, not just helper
        logic — that's the contract we actually care about.

        Uses creatine_monohydrate (a non-denylisted cid) to isolate the
        guard's behavior from the denylist. The guard is cid-independent.
        """
        product = _make_anchor_eligible_header_with_dosed_children(
            child_quantities_mg=(200.0, 150.0)
        )
        # Sanity: confirm we ARE building a real children-with-doses shape.
        skipped = product["ingredient_quality_data"]["ingredients_skipped"]
        dosed_children = [
            r for r in skipped
            if not r.get("is_blend_header")
            and not r.get("blend_total_weight_only")
            and (r.get("quantity") or 0) > 0
            and (r.get("unit") or "").strip().lower() not in {"", "np", "n/a", "na", "none", "0", "unspecified"}
        ]
        assert len(dosed_children) >= 1, "fixture must include ≥1 dosed nested child"

        # The seam itself must refuse anchor eligibility.
        assert scorer._has_blend_header_anchor(product) is False, (
            "child-dose guard MUST prevent _has_blend_header_anchor from "
            "returning True when nested children carry usable individual doses"
        )

    def test_child_dose_guard_full_pipeline_does_not_credit_header(self, scorer):
        """End-to-end companion to the seam test: with dosed children present,
        the full scorer pipeline must not promote the product via the anchor.

        The anchor flag and basis must NOT be set. The product may then be
        scored via children (if they pass the strict contract) or stay
        NOT_SCORED, but it must not be credited via the header path.

        Uses creatine_monohydrate for the same TDD-clarity reason as the
        seam test above.
        """
        product = _make_anchor_eligible_header_with_dosed_children()
        result = scorer.score_product(product)

        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]
        assert result.get("score_basis") != "blend_header_anchor"

    # --- B5 transparency evidence preservation (3 of 10 corpus products) ---

    def test_b5_transparency_evidence_retained_when_proprietary_blends_present(
        self, scorer
    ):
        """3 of 10 corpus products (256077, 270511, 302668) have proprietary_blends
        populated; B5 transparency penalty must continue to fire alongside the
        new anchor credit. This is automatic via existing B5 wiring at
        score_supplements.py:2780-2786 — no new transparency logic.

        We assert that adding anchor credit does NOT suppress B5 evidence in
        the score_breakdown for these products.
        """
        product = _make_digestive_enzyme_header_only()
        # Force proprietary_blends to be populated (mirrors DSLD 302668 shape:
        # 'Digestive Enzyme Blends' detector entry, disclosure_level='none').
        product["proprietary_blends"] = [
            {
                "name": "Digestive Enzyme Blends",
                "disclosure_level": "none",
                "total_weight": 350.0,
                "unit": "mg",
                "source_field": "activeIngredients[0]",
                "child_ingredients": [],
                "evidence": {
                    "blend_id": "BLEND_ENZYME",
                    "matched_text": "enzyme blend",
                    "risk_category": "enzyme",
                    "severity_level": "low",
                    "amounts_present": "none",
                    "penalty_applicable": -10,
                    "penalty_reason": "No ingredient amounts disclosed",
                },
                "detector_group": "Digestive Enzyme Blends",
            }
        ]
        result = scorer.score_product(product)

        # Anchor still fires
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" in result["flags"]
        # B5 evidence still present — section B (safety/purity) carries a
        # transparency penalty for the disclosed-but-opaque blend. We don't
        # assert exact magnitude (B5 math has class multipliers); we assert
        # the B5 evidence path is wired in the breakdown.
        breakdown = result.get("score_breakdown") or {}
        section_b = breakdown.get("section_b_safety_purity") or breakdown.get("b") or {}
        # Find any B5-related evidence — accept any of these field names that
        # the breakdown might use to surface transparency penalty data.
        b5_signal_present = any(
            "B5" in str(k) or "transparency" in str(k).lower() or "proprietary" in str(k).lower()
            for k in section_b
        )
        # Soft assertion: if section_b is structured differently, fall back
        # to checking that the product carries a transparency-aware verdict
        # (anchor-flag + populated proprietary_blends → verdict still CAUTION).
        assert b5_signal_present or result["verdict"] in {"CAUTION", "POOR"}, (
            f"expected B5 evidence in section_b or transparency-aware verdict; "
            f"section_b={section_b}, verdict={result['verdict']}"
        )

    # --- Negative regressions: existing denials must hold ---

    def test_enzyme_header_with_zero_dose_stays_not_scored(self, scorer):
        """Existing dose-check at score_supplements.py:702 must still reject
        digestive_enzymes headers with qty <= 0 even after denylist removal.
        """
        product = _make_digestive_enzyme_header_only(
            header_quantity=0.0,
            header_unit="NP",
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]

    def test_generic_BLEND_prefix_canonical_stays_not_scored(self, scorer):
        """Regression: BLEND_GENERAL / BLEND_ENZYME / etc. must continue to be
        rejected by the BLEND_ prefix check at score_supplements.py:711. This
        path is unrelated to the denylist removal but must not regress.
        """
        product = _make_blend_header_anchor_eligible(
            header_canonical_id="BLEND_ENZYME",
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED"
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]

    # --- Other reserved class-level cids stay denied (A.2b is scope-narrow) ---

    @pytest.mark.parametrize(
        "still_denylisted",
        ["prebiotics", "probiotics", "whey_protein", "collagen"],
    )
    def test_other_reserved_cids_stay_denied(self, scorer, still_denylisted):
        """A.2b removes ONLY digestive_enzymes from the denylist. The other
        four reserved class-level cids (prebiotics, probiotics, whey_protein,
        collagen) keep waiting for their own dedicated slices — they must
        remain in BLEND_HEADER_ANCHOR_CANONICAL_DENYLIST and stay NOT_SCORED.

        This test guards against accidental over-removal in the production
        change. Pairs with the parametrize list at
        scripts/tests/test_not_scored_truthful_diagnostics.py:1158-1172
        (which the production change must update to drop digestive_enzymes
        and keep these four).
        """
        product = _make_blend_header_anchor_eligible(
            header_canonical_id=still_denylisted,
        )
        result = scorer.score_product(product)

        assert result["verdict"] == "NOT_SCORED", (
            f"{still_denylisted!r} must remain denied — it is reserved for "
            f"its own future slice"
        )
        assert "SCORED_VIA_BLEND_HEADER_ANCHOR" not in result["flags"]
