#!/usr/bin/env python3
"""A user-visible 0/20 must mean a REVIEWED conclusion — never a coverage gap.

3,995 products were showing Evidence 0/20 because PharmaGuide had not reviewed
their ingredients yet. The scorer already knew the difference: _evidence_result_state
has said so since it was written, and its own docstring reads "A missing review
record is a coverage gap, never proof of weak evidence." The information was
computed and then thrown away before it reached anyone.

These tests pin the public meaning of that state. They do not introduce a second
state machine: evidence_display_state maps the states the scorer already emits,
and lives beside the copy map that is already keyed by them.
"""
from scoring_v4.quality_score import (
    EVIDENCE_COVERAGE_GAP_STATES, EVIDENCE_REVIEWED_ZERO_STATES,
    _EVIDENCE_ZERO_REASON, _config, _pillar_evidence, evidence_display_state)


def _evidence(state, raw=0.0):
    return _pillar_evidence({"score": raw, "metadata": {"evidence_result_state": state}},
                            20, "generic_single_molecule", _config())


# ── 1. an unreviewed active must not render as a reviewed zero ────────────────

def test_an_unreviewed_active_is_not_presented_as_zero_evidence():
    pillar = _evidence("clinical_review_not_covered")

    assert pillar["display_state"] == "not_yet_reviewed"
    assert pillar["evidence_result_state"] == "clinical_review_not_covered"
    assert "pending" in pillar["reason"].lower()
    # The old copy read as an internal database limitation leaking into the product.
    assert "does not yet cover" not in pillar["reason"]


def test_an_incomplete_strain_review_is_also_a_coverage_gap():
    assert evidence_display_state("native_research_review_incomplete") == "not_yet_reviewed"
    assert evidence_display_state("human_clinical_evidence_unestablished") == "not_yet_reviewed"


# ── 2/3. reviewed zeros stay zeros, and stay distinguishable ──────────────────

def test_a_reviewed_null_is_a_legitimate_zero():
    pillar = _evidence("evaluated_null")

    assert pillar["score"] == 0
    assert pillar["display_state"] == "assessed"
    assert "reviewed" in pillar["reason"].lower()


def test_no_qualifying_human_evidence_is_a_reviewed_zero_with_its_own_copy():
    null_reason = _evidence("evaluated_null")["reason"]
    unqualified = _evidence("no_qualifying_human_evidence")

    assert unqualified["display_state"] == "assessed"
    assert unqualified["reason"] != null_reason


def test_the_two_kinds_of_zero_never_overlap():
    """The whole point. If a state ever landed in both sets, the invariant that
    a visible zero means a reviewed conclusion would be unenforceable."""
    assert not (EVIDENCE_REVIEWED_ZERO_STATES & EVIDENCE_COVERAGE_GAP_STATES)


def test_every_zero_state_with_copy_has_a_display_meaning():
    """Guard against a new state being added to the copy map and silently
    defaulting to 'assessed' - which would reintroduce the original bug."""
    for state in _EVIDENCE_ZERO_REASON:
        display = evidence_display_state(state)
        assert display in {"assessed", "not_yet_reviewed",
                           "applicability_unestablished", "not_applicable"}
        if state in EVIDENCE_COVERAGE_GAP_STATES:
            assert display == "not_yet_reviewed", state


# ── 4. reviewed-but-inapplicable is neither of the above ──────────────────────

def test_applicability_unresolved_is_neither_unreviewed_nor_a_verdict():
    pillar = _evidence("applicability_unestablished")

    assert pillar["display_state"] == "applicability_unestablished"
    assert pillar["display_state"] != "not_yet_reviewed"
    assert "reviewed" in pillar["reason"].lower()
    assert "pending" not in pillar["reason"].lower()


def test_no_assessable_actives_is_not_applicable_rather_than_a_failure():
    assert evidence_display_state("no_assessable_actives") == "not_applicable"


# ── 5. assessment state governs display, not score points ────────────────────

def test_assessment_state_governs_display_not_score():
    """Phase 5 doctrine: Assessment state must come from the canonical Evidence
    disposition, never inferred from a positive score. A coverage gap must never
    render as assessed simply because score > 0."""
    for gap in ["clinical_review_not_covered", "identity_material_unresolved", "literature_resolution_required"]:
        assert evidence_display_state(gap) == "not_yet_reviewed"
    assert evidence_display_state("evaluated_applicable") == "assessed"
    assert evidence_display_state("evaluated_authority") == "assessed"
    assert evidence_display_state("no_qualifying_human_evidence") == "assessed"


def test_the_pillar_still_reports_the_raw_zero_for_scoring():
    """Presentation changes; the score does not. The five known pillars are NOT
    renormalised to 100 - that would hand out free credit for missing evidence."""
    pillar = _evidence("clinical_review_not_covered")

    assert pillar["score"] == 0
    assert pillar["max"] == 20
