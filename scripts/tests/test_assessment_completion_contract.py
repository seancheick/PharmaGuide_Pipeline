"""A number can exist without the assessment behind it being complete.

quality_score_status and quality_assessment_status answer different questions:

    quality_score_status       did the engine produce a usable number?
    quality_assessment_status  did PharmaGuide finish the assessment?

Collapsing them published a definitive tier for 4,117 products whose Evidence
pillar contributed 0 of 20 because no reviewed record matched any active on the
label. These tests pin the two facts apart.
"""

from scoring_v4.scored_artifact import _quality_assessment_status


def _pillars(display_state):
    return {"evidence": {"score": 0.0, "max": 20, "display_state": display_state}}


def test_unreviewed_evidence_makes_a_scored_product_partial():
    assert (
        _quality_assessment_status("scored", {}, _pillars("not_yet_reviewed"))
        == "partial"
    )


def test_reviewed_zero_stays_complete():
    # A reviewed conclusion of zero is a finished assessment.
    assert (
        _quality_assessment_status("scored", {}, _pillars("assessed")) == "complete"
    )


def test_applicability_unestablished_stays_complete():
    # Records were found and reviewed; failing to apply to this label IS the
    # completed product-level conclusion.
    assert (
        _quality_assessment_status(
            "scored", {}, _pillars("applicability_unestablished")
        )
        == "complete"
    )


def test_a_weak_product_is_still_partial_when_evidence_is_unreviewed():
    # Weak other pillars do not make the sixth pillar assessed. No percentile
    # or "does it look good enough" rule may enter this decision.
    pillars = {
        "evidence": {"score": 0.0, "max": 20, "display_state": "not_yet_reviewed"},
        "formulation": {"score": 1.0, "max": 20},
        "dose": {"score": 1.0, "max": 20},
    }
    assert _quality_assessment_status("scored", {}, pillars) == "partial"


def test_missing_pillars_do_not_crash_or_invent_completion():
    assert _quality_assessment_status("scored", {}, None) == "complete"
    assert _quality_assessment_status("scored", {}, {}) == "complete"


def test_dose_safety_unresolved_still_wins():
    dose = {"state_counts": {"material_but_unresolved": 2}}
    assert _quality_assessment_status("scored", dose, _pillars("assessed")) == "partial"


def test_not_scored_and_failed_semantics_are_unchanged():
    assert _quality_assessment_status("not_scored", {}, None) == "partial"
    assert _quality_assessment_status("suppressed_safety", {}, None) == "complete"
    assert _quality_assessment_status("anything_else", {}, None) == "failed"


def test_suppressed_safety_with_unreviewed_evidence_is_partial():
    # A safety-suppressed product whose Evidence was never reviewed has still
    # not been fully assessed; the suppression is about the number, not the
    # completeness of the review.
    assert (
        _quality_assessment_status(
            "suppressed_safety", {}, _pillars("not_yet_reviewed")
        )
        == "partial"
    )
