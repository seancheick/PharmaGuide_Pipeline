from scoring_v4.confidence import _clinical_matches


def test_confidence_cannot_reintroduce_a_rejected_context_reference():
    assert _clinical_matches({"evidence_data": {"clinical_matches": [{
        "id": "INGR_VITAMIN_A_BETA_CAROTENE", "evidence_level": "ingredient-human",
        "study_type": "systematic_review_meta",
    }]}}) == []
