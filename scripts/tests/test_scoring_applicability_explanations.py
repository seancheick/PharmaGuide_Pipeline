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
    from scoring_v4.quality_score import _config
    pillar = _pillar_evidence({"score": 18, "metadata": {
        "primary_evidence_floor": 18, "primary_evidence_floor_canonical": "ksm 66",
    }}, 20, "generic_botanical_branded", _config())
    assert "primary ingredient" in pillar["reason"].lower()
    assert "whole formula" in pillar["reason"].lower()
