"""Public reasons must describe the facts, not guess from a numeric band."""

from scoring_v4.quality_score import _pillar_from_dim, _pillar_evidence


def test_complete_disclosure_is_not_called_missing_because_claim_bonus_absent():
    pillar = _pillar_from_dim("transparency", {
        "score": 11, "max": 15,
        "metadata": {"panel_active_count": 10, "panel_named_count": 10,
                     "panel_dose_count": 10, "panel_identity_coverage": 1.0,
                     "panel_dose_coverage": 1.0},
    }, 15, "transparency")
    assert pillar["score"] == 11
    assert "fully disclosed" in pillar["reason"]
    assert "aren't" not in pillar["reason"]


def test_real_disclosure_gap_is_not_hidden_by_other_points():
    pillar = _pillar_from_dim("transparency", {
        "score": 13, "max": 15,
        "metadata": {"panel_active_count": 10, "panel_named_count": 10,
                     "panel_dose_count": 5, "panel_identity_coverage": 1.0,
                     "panel_dose_coverage": .5},
    }, 15, "transparency")
    assert "not all" in pillar["reason"].lower()


def test_a_blend_with_undisclosed_amounts_is_never_called_fully_transparent():
    # URO Vaginal Moisture + Mood: 600 mg disclosed, a 295 mg blend whose five
    # members carry no amounts. A high band must not claim every amount is shown.
    pillar = _pillar_from_dim("transparency", {
        "score": 8.0, "max": 10.0,
        "penalties": {"B5_proprietary_blend_opacity": -1.99},
        "metadata": {"flags": ["PROPRIETARY_BLEND_PRESENT"]},
    }, 15, "transparency")
    assert pillar["score"] == 12.0
    assert "every amount is disclosed" not in pillar["reason"]
    assert "blend" in pillar["reason"].lower()


def test_primary_ingredient_floor_is_not_whole_formula_efficacy_claim():
    """When the floor DID drive the credit, say so — and do not imply the whole
    formula was trialled."""
    from scoring_v4.quality_score import _config
    pillar = _pillar_evidence({"score": 18, "metadata": {
        "evidence_result_state": "evaluated_applicable",  # every real artifact declares it
        "primary_evidence_floor": 18, "primary_evidence_floor_canonical": "ksm 66",
        "primary_evidence_floor_decisive": True,
    }}, 20, "generic_botanical_branded", _config())
    assert "primary ingredient" in pillar["reason"].lower()
    assert "whole formula" in pillar["reason"].lower()


def test_a_shadowed_floor_does_not_claim_it_drove_the_credit():
    """A floor that was COMPUTED is not a floor that DROVE the score.

    For 458 products the pipeline already exceeds the floor, so the floor changes
    nothing. Telling those readers their credit came from the primary ingredient
    is a false explanation of a true score.
    """
    from scoring_v4.quality_score import _config
    pillar = _pillar_evidence({"score": 18, "metadata": {
        "primary_evidence_floor": 11, "primary_evidence_floor_canonical": "ksm 66",
        "primary_evidence_floor_decisive": False,
    }}, 20, "generic_botanical_branded", _config())
    assert "primary ingredient" not in pillar["reason"].lower()


def test_the_floor_owner_itself_uses_a_strict_comparison():
    """The other half of the equality edge, at the layer that DECIDES it.

    The two tests above hand `primary_evidence_floor_decisive` to the copy layer,
    so they pin that the copy reads the fact - but they would still pass if
    generic_evidence started computing that fact with `>=`. This drives the owner
    instead, on the degenerate product where floor and pipeline are both 0.0. If
    the comparison ever loosens, a product with no evidence at all would report a
    decisive floor and be told the primary ingredient drove its score of zero.
    """
    from scoring_v4.modules.generic_evidence import score_evidence

    payload = score_evidence({}, apply_primary_floor=True)

    assert payload["metadata"]["primary_evidence_floor"] == 0.0
    assert payload["metadata"]["primary_evidence_floor_decisive"] is False


def test_the_decisive_verdict_comes_from_the_floor_owner_not_a_recomputation():
    """quality_score must not re-derive decisiveness from the floor value. If it
    did, a floor equal to the pipeline would read as floor-driven — and equality
    is not a raise."""
    from scoring_v4.quality_score import _config
    pillar = _pillar_evidence({"score": 18, "metadata": {
        "primary_evidence_floor": 18, "primary_evidence_floor_canonical": "ksm 66",
        "primary_evidence_floor_decisive": False,   # owner says: equal, not raised
    }}, 20, "generic_botanical_branded", _config())
    assert "primary ingredient" not in pillar["reason"].lower()


def test_disclosed_panel_with_opaque_blends_is_not_called_fully_disclosed():
    # GNC Sport Milk Chocolate (DSLD 1060): every panel row carries an amount,
    # but five proprietary blends hide member amounts and cost 10 points.
    pillar = _pillar_from_dim("transparency", {
        "score": 1.0, "max": 15.0,
        "penalties": {"B5_proprietary_blend_opacity": -10.0},
        "metadata": {"panel_active_count": 20, "panel_named_count": 20,
                     "panel_dose_count": 20, "flags": ["PROPRIETARY_BLEND_PRESENT"]},
    }, 15, "transparency")
    assert "fully disclosed" not in pillar["reason"]
    assert pillar["reason"] == (
        "Amounts outside the proprietary blends are disclosed, but the blends "
        "hide their individual ingredient amounts."
    )


def test_panel_gap_and_opaque_blends_are_both_named():
    pillar = _pillar_from_dim("transparency", {
        "score": 2.0, "max": 15.0,
        "penalties": {"B5_proprietary_blend_opacity": -6.0},
        "metadata": {"panel_active_count": 10, "panel_named_count": 10,
                     "panel_dose_count": 7, "flags": ["PROPRIETARY_BLEND_PRESENT"]},
    }, 15, "transparency")
    assert pillar["reason"] == (
        "Not all active ingredient identities or individual amounts are disclosed, "
        "and proprietary blends hide their individual ingredient amounts."
    )


def test_omega_transparency_names_what_is_missing_not_amounts():
    # Thorne Advanced DHA (DSLD 298106): EPA/DHA amounts and source are printed,
    # the molecular form is not. Oxidation testing is no longer named here — the
    # pillar stopped scoring it, so it stopped being a Transparency gap.
    from scoring_v4.quality_score import _omega_transparency_reason

    dim = {"score": 9.0, "components": {"epa_or_dha_disclosed": 5.0, "source_disclosed": 3.0,
                                         "b3_claim_compliance": 1.0}, "penalties": {}}
    assert _omega_transparency_reason(dim, "fallback") == (
        "EPA/DHA amounts and the marine or algal source are disclosed; "
        "the molecular form is not."
    )


def test_omega_transparency_blend_opacity_is_named():
    from scoring_v4.quality_score import _omega_transparency_reason

    dim = {"components": {"source_disclosed": 3.0},
           "penalties": {"B5_proprietary_blend_opacity": -2.0}}
    assert _omega_transparency_reason(dim, "fallback") == (
        "The marine or algal source is disclosed; EPA/DHA amounts and the molecular form "
        "are not. A proprietary blend hides individual amounts."
    )


def test_an_unrated_ingredient_form_is_neutral_not_zero():
    """Nature's Bounty Ultra Soya Lecithin (17091): lecithin has no form rating,
    so Formulation read 0/20 while Dose on the same product gave partial credit
    for an unavailable benchmark. Unknown is neutral, not worst-case."""
    from scoring_v4.quality_score import _config, _pillar_formulation

    dim = {"score": 0.0, "max": 30.0, "metadata": {
        "iqm_form_quality_assessed_count": 0, "formulation_profile": "generic_iqm"}}
    pillar = _pillar_formulation(dim, 20, "generic_single_molecule", _config())

    assert pillar["score"] == 12.0  # the module's own neutral floor, 0.6 of the pillar
    assert "not rated" in pillar["reason"].lower()


def test_a_rated_but_weak_form_is_not_lifted_to_neutral():
    """Only 'we have not rated this' is neutral. A form we DID rate stays low."""
    from scoring_v4.quality_score import _config, _pillar_formulation

    dim = {"score": 4.0, "max": 30.0, "metadata": {
        "iqm_form_quality_assessed_count": 2, "formulation_profile": "generic_iqm"}}
    pillar = _pillar_formulation(dim, 20, "generic_single_molecule", _config())

    assert pillar["score"] < 12.0


def test_omega_transparency_never_names_a_disclosure_it_stopped_scoring():
    """Oxidation testing left Transparency on 2026-09-18 (omega_rubric
    oxidation_disclosed.score = 0, cap 15 -> 13). While the explanation still
    listed it, every omega label was told oxidation testing was missing for a
    pillar that no longer scores it, and the "everything is disclosed" sentence
    could never be reached — no label can earn a retired component."""
    from scoring_v4.quality_score import _omega_transparency_reason

    fully_disclosed = {"components": {"epa_or_dha_disclosed": 5.0, "source_disclosed": 3.0,
                                      "form_disclosed": 4.0}, "penalties": {}}
    reason = _omega_transparency_reason(fully_disclosed, "fallback")

    assert "oxidation" not in reason.lower()
    assert reason == "EPA/DHA amounts, the molecular form and the source are all disclosed."
