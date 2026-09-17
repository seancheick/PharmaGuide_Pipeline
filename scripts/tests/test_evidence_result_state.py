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
    assert _state(_product(matches=[])) == "clinical_review_not_covered"


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
        "PharmaGuide's clinical evidence review does not yet cover the ingredients on this "
        "label. This is a gap in our review, not a finding of weak evidence."
    )


def test_zero_state_copy_is_specific():
    assert _zero_reason("applicability_unestablished") == (
        "Recorded research does not match this label's ingredient form, dose or delivery, "
        "so it earns no evidence credit here."
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
    assert reason.startswith("PharmaGuide's clinical evidence review does not yet cover")


def test_review_gap_and_undisclosed_strain_dose_are_both_named():
    # Garden of Life Once Daily Ultra 90 Billion (DSLD 173776): NCFM research awaits
    # review AND the label gives no per-strain CFU. Both limits are real: review
    # can add research credit, the missing amounts block dose matching.
    from scoring_v4.modules.probiotic_evidence import score_evidence as probiotic_evidence
    from test_probiotic_applicability_rubric import strain_product

    product = strain_product(clinical_id="STRAIN_ACIDOPHILUS_NCFM",
                             name="Lactobacillus acidophilus NCFM", dose=None)
    evidence = probiotic_evidence(product)
    assert evidence["score"] == 0
    assert evidence["metadata"]["evidence_result_state"] == "native_research_review_incomplete"
    reason = _pillar_evidence(evidence, 20, "probiotic", _config())["reason"]
    assert reason.endswith(
        "Individual strain amounts are also not disclosed, so no strain can be matched to a "
        "studied dose."
    )
    assert "review is incomplete" in reason


def test_dosed_strain_review_gap_does_not_mention_dose():
    from scoring_v4.modules.probiotic_evidence import score_evidence as probiotic_evidence
    from test_probiotic_applicability_rubric import strain_product

    product = strain_product(clinical_id="STRAIN_ACIDOPHILUS_NCFM",
                             name="Lactobacillus acidophilus NCFM", dose=1e9)
    reason = _pillar_evidence(probiotic_evidence(product), 20, "probiotic", _config())["reason"]
    assert "not disclosed" not in reason
