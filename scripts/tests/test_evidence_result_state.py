"""Evidence = 0 must say why: no review coverage is not weak evidence.

The generic Evidence scorer records one result state from the same matches it
scores, and the public pillar explains a zero from that state.
"""

from scoring_v4.modules.generic_evidence import score_evidence
from scoring_v4.quality_score import _config, _pillar_evidence
from tests.test_v4_generic_evidence_p133 import _match, _product


def _state(product):
    return score_evidence(product)["metadata"]["evidence_result_state"]


def test_active_without_any_reviewed_record_is_not_covered():
    unreviewed_prod = _product(
        ingredients=[{"canonical_id": "unreviewed_herb", "name": "Unreviewed Herb", "cleaner_row_role": "active_scorable"}],
        matches=[],
    )
    assert _state(unreviewed_prod) == "clinical_review_not_covered"


def test_essential_nutrient_without_clinical_rct_is_authority_supported():
    """Essential minerals with established DRI authority resolve to evaluated_authority."""
    assert _state(_product(matches=[])) == "evaluated_authority"


def test_records_rejected_by_applicability_are_not_called_uncovered():
    match = _match(id="TEST_FORMULA_ONLY", applicability={"scope": "formula_context_only"})
    assert _state(_product(matches=[match])) == "applicability_unestablished"


def test_negative_review_is_unfavorable():
    assert _state(_product(matches=[_match(effect_direction="negative")])) == "evaluated_unfavorable"


def test_credited_evidence_is_applicable():
    assert _state(_product()) == "evaluated_applicable"


def test_no_scorable_active_is_its_own_state():
    product = _product(ingredients=[], matches=[])
    assert _state(product) == "no_assessable_actives"


def _zero_reason(state):
    dim = {"score": 0.0, "metadata": {"evidence_result_state": state}}
    return _pillar_evidence(dim, 20, "generic_single_molecule", _config())["reason"]


def test_zero_without_review_coverage_never_says_limited_evidence():
    reason = _zero_reason("clinical_review_not_covered")
    assert "limited" not in reason.lower()
    assert reason == (
        "Clinical evidence review pending. We haven't completed our evidence review for the "
        "ingredients on this label yet. This does not mean they lack clinical evidence."
    )


def test_zero_state_copy_is_specific():
    assert _zero_reason("applicability_unestablished") == (
        "We reviewed the evidence for these ingredients, but it does not match this label's "
        "form, dose or delivery, so it cannot be applied to this product."
    )
    assert _zero_reason("evaluated_unfavorable") == (
        "Reviewed human research did not show benefit for these ingredients."
    )
    assert _zero_reason("no_assessable_actives") == (
        "No active ingredient on this label could be assessed for clinical evidence."
    )


def test_nested_multi_state_is_read_through_generic_metadata():
    dim = {"score": 0.0, "metadata": {"generic_evidence_metadata": {
        "evidence_result_state": "clinical_review_not_covered"}}}
    reason = _pillar_evidence(dim, 20, "prenatal_multi", _config())["reason"]
    assert reason.startswith("Clinical evidence review pending.")


_UNDISCLOSED = ("Individual strain amounts are also not disclosed, so no strain can be "
                "matched to a studied dose.")


def test_review_gap_and_undisclosed_strain_dose_are_both_named():
    # An uncurated strain stub (La-14) on a label with no per-strain CFU: the
    # review is genuinely unfinished AND the missing amounts block dose matching.
    from scoring_v4.modules.probiotic_evidence import score_evidence as probiotic_evidence
    from test_probiotic_applicability_rubric import strain_product

    product = strain_product(clinical_id="STRAIN_ACIDOPHILUS_LA14",
                             name="Lactobacillus acidophilus La-14", dose=None)
    evidence = probiotic_evidence(product)
    assert evidence["score"] == 0
    assert evidence["metadata"]["evidence_result_state"] == "native_research_review_incomplete"
    reason = _pillar_evidence(evidence, 20, "probiotic", _config())["reason"]
    assert reason.endswith(_UNDISCLOSED)
    assert "review is incomplete" in reason


def test_finished_review_still_names_undisclosed_strain_amounts():
    # NCFM's contexts are clinician-approved (a finished review); the label still
    # gives no per-strain CFU, and that separate limit must stay visible.
    from scoring_v4.modules.probiotic_evidence import score_evidence as probiotic_evidence
    from test_probiotic_applicability_rubric import strain_product

    product = strain_product(clinical_id="STRAIN_ACIDOPHILUS_NCFM",
                             name="Lactobacillus acidophilus NCFM", dose=None)
    evidence = probiotic_evidence(product)
    assert evidence["metadata"]["evidence_result_state"] == "applicability_unestablished"
    reason = _pillar_evidence(evidence, 20, "probiotic", _config())["reason"]
    assert reason.endswith(_UNDISCLOSED)
    assert "review is incomplete" not in reason


def test_dosed_strain_review_gap_does_not_mention_dose():
    from scoring_v4.modules.probiotic_evidence import score_evidence as probiotic_evidence
    from test_probiotic_applicability_rubric import strain_product

    product = strain_product(clinical_id="STRAIN_ACIDOPHILUS_NCFM",
                             name="Lactobacillus acidophilus NCFM", dose=1e9)
    reason = _pillar_evidence(probiotic_evidence(product), 20, "probiotic", _config())["reason"]
    assert "not disclosed" not in reason


def test_every_zero_state_has_copy_that_is_not_the_numeric_band():
    """The state sets and the copy map must not drift apart.

    A zero state that falls through to the band copy would tell the user
    "Limited human evidence for these ingredients." - a reviewed finding of
    weakness. For a coverage gap or an applicability gap that sentence is false,
    and it is the exact defect the display-state work exists to prevent.
    """
    from scoring_v4.quality_score import (
        EVIDENCE_APPLICABILITY_STATES,
        EVIDENCE_COVERAGE_GAP_STATES,
        EVIDENCE_NOT_APPLICABLE_STATES,
        EVIDENCE_REVIEWED_ZERO_STATES,
    )

    from scoring_v4.quality_score import _reason_evidence

    band = _reason_evidence("low")
    every_state = (EVIDENCE_REVIEWED_ZERO_STATES | EVIDENCE_COVERAGE_GAP_STATES
                   | EVIDENCE_APPLICABILITY_STATES | EVIDENCE_NOT_APPLICABLE_STATES)
    assert every_state, "state sets are empty - the contract has moved"
    for state in sorted(every_state):
        assert _zero_reason(state) != band, state


def test_a_coverage_gap_zero_never_reads_as_a_reviewed_weakness():
    from scoring_v4.quality_score import EVIDENCE_COVERAGE_GAP_STATES

    for state in sorted(EVIDENCE_COVERAGE_GAP_STATES):
        reason = _zero_reason(state).lower()
        assert "limited" not in reason, state
        assert "did not show" not in reason, state
